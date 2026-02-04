import requests
from app.core.config import TODOIST_API_TOKEN
from app.core.logger import setup_logger

logger = setup_logger(__name__)

ACTION_REGISTRY = {}

def register_action(name):
    """Decorator to register an action handler."""
    def decorator(func):
        ACTION_REGISTRY[name] = func
        return func
    return decorator

def get_tasks():
    """Fetches active tasks from Todoist."""
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {"Authorization": f"Bearer {TODOIST_API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return []

def get_projects():
    """Fetches projects from Todoist."""
    url = "https://api.todoist.com/rest/v2/projects"
    headers = {"Authorization": f"Bearer {TODOIST_API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        return []

@register_action('close_task')
def handle_close_task(action, headers, dry_run=False):
    task_id = action.get('id')
    if not task_id:
        raise ValueError("Missing 'id' for close_task")
    
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}/close"
    
    if dry_run:
        return "simulated", f"Would close task {task_id}", f"POST {url}"

    requests.post(url, headers=headers).raise_for_status()
    logger.info(f"Closed task: {task_id}")
    return "success", f"Closed task {task_id}", f"POST {url}"

@register_action('update_task')
def handle_update_task(action, headers, dry_run=False):
    task_id = action.get('id')
    if not task_id:
        raise ValueError("Missing 'id' for update_task")
    
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    data = {k: v for k, v in action.items() if k not in ['type', 'id']}
    
    if dry_run:
        return "simulated", f"Would update task {task_id} with {data}", f"POST {url} with {data}"

    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Updated task: {task_id}")
    return "success", f"Updated task {task_id}", f"POST {url}"

@register_action('create_project')
def handle_create_project(action, headers, dry_run=False):
    url = "https://api.todoist.com/rest/v2/projects"
    data = {"name": action.get('name')}
    
    if dry_run:
        return "simulated", f"Would create project '{action.get('name')}'", f"POST {url} with {data}"

    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Created project: {action.get('name')}")
    return "success", f"Created project {action.get('name')}", f"POST {url}"

@register_action('create_task')
def handle_create_task(action, headers, dry_run=False):
    url = "https://api.todoist.com/rest/v2/tasks"
    data = {k: v for k, v in action.items() if k not in ['type']}
    
    if dry_run:
        return "simulated", f"Would create task '{action.get('content')}'", f"POST {url} with {data}"

    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Created task: {action.get('content')}")
    return "success", f"Created task {action.get('content')}", f"POST {url}"

@register_action('create_label')
def handle_create_label(action, headers, dry_run=False):
    url = "https://api.todoist.com/rest/v2/labels"
    data = {"name": action.get('name')}
    
    if dry_run:
        return "simulated", f"Would create label '{action.get('name')}'", f"POST {url} with {data}"

    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Created label: {action.get('name')}")
    return "success", f"Created label {action.get('name')}", f"POST {url}"

@register_action('add_label')
def handle_add_label(action, headers, dry_run=False):
    """Adds a label to a task by appending to existing labels."""
    task_id = action.get('task_id')
    label = action.get('label')
    if not task_id or not label:
        raise ValueError("Missing 'task_id' or 'label' for add_label")
    
    get_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    update_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"

    if dry_run:
        return "simulated", f"Would add label '{label}' to task {task_id}", f"GET {get_url} -> POST {update_url}"

    # First fetch the task to get current labels
    task_resp = requests.get(get_url, headers=headers)
    task_resp.raise_for_status()
    current_labels = task_resp.json().get('labels', [])
    
    if label not in current_labels:
        current_labels.append(label)
        requests.post(update_url, headers=headers, json={'labels': current_labels}).raise_for_status()
        logger.info(f"Added label '{label}' to task {task_id}")
        return "success", f"Added label '{label}' to task {task_id}", f"POST {update_url}"
    else:
        logger.info(f"Label '{label}' already exists on task {task_id}")
        return "success", f"Label '{label}' already exists", f"GET {get_url}"

@register_action('remove_label')
def handle_remove_label(action, headers, dry_run=False):
    """Removes a label from a task."""
    task_id = action.get('task_id')
    label = action.get('label')
    if not task_id or not label:
        raise ValueError("Missing 'task_id' or 'label' for remove_label")
    
    get_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    update_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"

    if dry_run:
        return "simulated", f"Would remove label '{label}' from task {task_id}", f"GET {get_url} -> POST {update_url}"

    # First fetch
    task_resp = requests.get(get_url, headers=headers)
    task_resp.raise_for_status()
    current_labels = task_resp.json().get('labels', [])
    
    if label in current_labels:
        current_labels.remove(label)
        requests.post(update_url, headers=headers, json={'labels': current_labels}).raise_for_status()
        logger.info(f"Removed label '{label}' from task {task_id}")
        return "success", f"Removed label '{label}' from task {task_id}", f"POST {update_url}"
    else:
        logger.info(f"Label '{label}' not found on task {task_id}")
        return "success", f"Label '{label}' not found", f"GET {get_url}"

@register_action('create_section')
def handle_create_section(action, headers, dry_run=False):
    url = "https://api.todoist.com/rest/v2/sections"
    data = {
        "name": action.get('name'),
        "project_id": action.get('project_id')
    }
    
    if dry_run:
        return "simulated", f"Would create section '{action.get('name')}'", f"POST {url} with {data}"

    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Created section: {action.get('name')}")
    return "success", f"Created section {action.get('name')}", f"POST {url}"

@register_action('move_task')
def handle_move_task(action, headers, dry_run=False):
    """Moves a task to a different project or section."""
    task_id = action.get('id')
    project_id = action.get('project_id')
    section_id = action.get('section_id')
    
    if not task_id:
        raise ValueError("Missing 'id' for move_task")
        
    data = {}
    if project_id:
        data['project_id'] = project_id
    if section_id:
        data['section_id'] = section_id
        
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    
    if not data:
        logger.warning("No destination provided for move_task")
        return "failed", "No destination provided", ""

    if dry_run:
        return "simulated", f"Would move task {task_id} to {data}", f"POST {url} with {data}"

    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Moved task {task_id}")
    return "success", f"Moved task {task_id}", f"POST {url}"

@register_action('add_comment')
def handle_add_comment(action, headers, dry_run=False):
    url = "https://api.todoist.com/rest/v2/comments"
    data = {
        "task_id": action.get('task_id'),
        "content": action.get('content')
    }
    
    if dry_run:
        return "simulated", f"Would add comment to task {action.get('task_id')}", f"POST {url} with {data}"

    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Added comment to task {action.get('task_id')}")
    return "success", f"Added comment to task", f"POST {url}"

def execute_todoist_action(action, api_token=TODOIST_API_TOKEN, dry_run=False):
    """
    Executes a single action using the registry.
    Returns: (status, message, api_call)
    """
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    action_type = action.get('type')
    handler = ACTION_REGISTRY.get(action_type)
    
    if handler:
        try:
            return handler(action, headers, dry_run=dry_run)
        except Exception as e:
            logger.error(f"Error executing {action_type}: {e}")
            return "failed", str(e), ""
    else:
        logger.warning(f"Unknown action type: {action_type}")
        return "failed", f"Unknown action type {action_type}", ""
