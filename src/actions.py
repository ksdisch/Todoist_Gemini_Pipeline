import requests
from src.logger import setup_logger

logger = setup_logger(__name__)

ACTION_REGISTRY = {}

def register_action(name):
    """Decorator to register an action handler."""
    def decorator(func):
        ACTION_REGISTRY[name] = func
        return func
    return decorator

@register_action('close_task')
def handle_close_task(action, headers):
    task_id = action.get('id')
    if not task_id:
        raise ValueError("Missing 'id' for close_task")
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}/close"
    requests.post(url, headers=headers).raise_for_status()
    logger.info(f"Closed task: {task_id}")

@register_action('update_task')
def handle_update_task(action, headers):
    task_id = action.get('id')
    if not task_id:
        raise ValueError("Missing 'id' for update_task")
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    data = {k: v for k, v in action.items() if k not in ['type', 'id']}
    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Updated task: {task_id}")

@register_action('create_project')
def handle_create_project(action, headers):
    url = "https://api.todoist.com/rest/v2/projects"
    data = {"name": action.get('name')}
    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Created project: {action.get('name')}")

@register_action('create_task')
def handle_create_task(action, headers):
    url = "https://api.todoist.com/rest/v2/tasks"
    data = {k: v for k, v in action.items() if k not in ['type']}
    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Created task: {action.get('content')}")

@register_action('create_label')
def handle_create_label(action, headers):
    url = "https://api.todoist.com/rest/v2/labels"
    data = {"name": action.get('name')}
    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Created label: {action.get('name')}")

@register_action('add_label')
def handle_add_label(action, headers):
    """Adds a label to a task by appending to existing labels."""
    task_id = action.get('task_id')
    label = action.get('label')
    if not task_id or not label:
        raise ValueError("Missing 'task_id' or 'label' for add_label")
    
    # First fetch the task to get current labels
    get_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    task_resp = requests.get(get_url, headers=headers)
    task_resp.raise_for_status()
    current_labels = task_resp.json().get('labels', [])
    
    if label not in current_labels:
        current_labels.append(label)
        update_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
        requests.post(update_url, headers=headers, json={'labels': current_labels}).raise_for_status()
        logger.info(f"Added label '{label}' to task {task_id}")
    else:
        logger.info(f"Label '{label}' already exists on task {task_id}")

@register_action('remove_label')
def handle_remove_label(action, headers):
    """Removes a label from a task."""
    task_id = action.get('task_id')
    label = action.get('label')
    if not task_id or not label:
        raise ValueError("Missing 'task_id' or 'label' for remove_label")
    
    # First fetch
    get_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    task_resp = requests.get(get_url, headers=headers)
    task_resp.raise_for_status()
    current_labels = task_resp.json().get('labels', [])
    
    if label in current_labels:
        current_labels.remove(label)
        update_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
        requests.post(update_url, headers=headers, json={'labels': current_labels}).raise_for_status()
        logger.info(f"Removed label '{label}' from task {task_id}")
    else:
        logger.info(f"Label '{label}' not found on task {task_id}")

@register_action('create_section')
def handle_create_section(action, headers):
    url = "https://api.todoist.com/rest/v2/sections"
    data = {
        "name": action.get('name'),
        "project_id": action.get('project_id')
    }
    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Created section: {action.get('name')}")

@register_action('move_task')
def handle_move_task(action, headers):
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
        
    if not data:
        logger.warning("No destination provided for move_task")
        return
    
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Moved task {task_id}")

@register_action('add_comment')
def handle_add_comment(action, headers):
    url = "https://api.todoist.com/rest/v2/comments"
    data = {
        "task_id": action.get('task_id'),
        "content": action.get('content')
    }
    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Added comment to task {action.get('task_id')}")

def execute_todoist_action(action, api_token):
    """Executes a single action using the registry."""
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    action_type = action.get('type')
    handler = ACTION_REGISTRY.get(action_type)
    
    if handler:
        try:
            handler(action, headers)
        except Exception as e:
            logger.error(f"Error executing {action_type}: {e}")
    else:
        logger.warning(f"Unknown action type: {action_type}")
