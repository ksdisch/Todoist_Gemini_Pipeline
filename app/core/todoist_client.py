import requests
from typing import Tuple, Optional, Dict, Any, Union
from app.core.config import TODOIST_API_TOKEN
from app.core.logger import setup_logger
from app.core.schemas import Action, ActionResult

logger = setup_logger(__name__)

# =================================================================================================
# TOUR HEADER: Todoist Client & Action Handlers
# =================================================================================================
#
# JOB: 
# This is the "Hands" of the application. It is the ONLY place that speaks to the outside world
# (Todoist API). If an HTTP request happens, it happens here.
#
# ARCHITECTURE:
# - Registry Pattern: We use a decorator @register_action to map string names ("close_task") 
#   to function handlers. This allows the Orchestrator to just say "execute 'close_task'" 
#   without knowing the details.
#
# KEY FEATURES:
# - Dry Run: Every handler supports a dry_run mode where it returns what it WOULD do without 
#   calling the API. This is critical for the "Plan -> Approve -> Execute" loop.
# - Undo Actions: Every handler is responsible for creating its own "Undo" recipe.
#   For example, if you create a task, the undo action is "delete_task" with the new ID.
#
# =================================================================================================

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

def get_sections():
    """Fetches sections from Todoist."""
    url = "https://api.todoist.com/rest/v2/sections"
    headers = {"Authorization": f"Bearer {TODOIST_API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching sections: {e}")
        return []

# Internal helpers for undo actions that aren't exposed to LLM directly but needed for undo
def _delete_helper(item_type: str, item_id: str, headers: Dict[str, str]) -> None:
    url = f"https://api.todoist.com/rest/v2/{item_type}/{item_id}"
    requests.delete(url, headers=headers).raise_for_status()

def _reopen_helper(task_id: str, headers: Dict[str, str]) -> None:
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}/reopen"
    requests.post(url, headers=headers).raise_for_status()

# Handlers

@register_action('close_task')
def handle_close_task(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    """
    Closes a task.
    
    HANDLER PATTERN EXPLANATION (Read this first):
    All handlers follow this structure:
    1. VALIDATE: Check that required fields (like 'id') are present.
    2. PREPARE UNDO: Define what the opposite action is (e.g. reopen_task).
    3. CHECK DRY_RUN: If True, return "simulated" and the undo action immediately.
    4. EXECUTE: Perform the real API request.
    5. RETURN: Success status and undo action.
    """
    task_id = action.get('id')
    if not task_id:
        raise ValueError("Missing 'id' for close_task")
    
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}/close"
    undo_action: Action = {"type": "reopen_task", "id": task_id}
    
    if dry_run:
        return "simulated", f"Would close task {task_id}", f"POST {url}", undo_action

    requests.post(url, headers=headers).raise_for_status()
    logger.info(f"Closed task: {task_id}")
    return "success", f"Closed task {task_id}", f"POST {url}", undo_action

@register_action('reopen_task')
def handle_reopen_task(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    # This is primarily an undo action, but could be used directly
    task_id = action.get('id')
    if not task_id:
        raise ValueError("Missing 'id' for reopen_task")
    
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}/reopen"
    # Undo of reopen is close
    undo_action: Action = {"type": "close_task", "id": task_id}
    
    if dry_run:
        return "simulated", f"Would reopen task {task_id}", f"POST {url}", undo_action

    requests.post(url, headers=headers).raise_for_status()
    logger.info(f"Reopened task: {task_id}")
    return "success", f"Reopened task {task_id}", f"POST {url}", undo_action

@register_action('update_task')
def handle_update_task(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    task_id = action.get('id')
    if not task_id:
        raise ValueError("Missing 'id' for update_task")
    
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    data = {k: v for k, v in action.items() if k not in ['type', 'id']}
    
    # Fetch original state for undo
    undo_action: Optional[Action] = None
    if not dry_run:
        try:
            original_task = requests.get(url, headers=headers).json()
            # Construct undo action with original values for the modified fields
            undo_data = {}
            for k in data.keys():
                if k in original_task:
                    undo_data[k] = original_task[k]
            
            if undo_data:
                undo_action = {"type": "update_task", "id": task_id, **undo_data}
        except Exception as e:
            logger.warning(f"Failed to fetch original task state for undo: {e}")

    if dry_run:
        # In dry run we can't really know the original state unless we fetch, 
        # but avoiding side effects means avoiding fetches? Actually GET is safe.
        # But for speed in dry run we might skip it or fake it.
        # Let's fake it for dry run to indicate it IS reversible
        undo_action = {"type": "update_task", "id": task_id, "content": "Original Content [Unknown in Dry Run]"}
        return "simulated", f"Would update task {task_id} with {data}", f"POST {url} with {data}", undo_action

    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Updated task: {task_id}")
    return "success", f"Updated task {task_id}", f"POST {url}", undo_action

@register_action('create_project')
def handle_create_project(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    url = "https://api.todoist.com/rest/v2/projects"
    data = {"name": action.get('name')}
    
    if dry_run:
        undo_action: Action = {"type": "delete_project", "id": "placeholder_id"}
        return "simulated", f"Would create project '{action.get('name')}'", f"POST {url} with {data}", undo_action

    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    project_id = resp.json().get('id')
    logger.info(f"Created project: {action.get('name')} ({project_id})")
    
    undo_action = {"type": "delete_project", "id": project_id}
    return "success", f"Created project {action.get('name')}", f"POST {url}", undo_action

@register_action('delete_project')
def handle_delete_project(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    # Internal action mostly for undo
    project_id = action.get('id')
    if not project_id:
         raise ValueError("Missing 'id' for delete_project")
    
    url = f"https://api.todoist.com/rest/v2/projects/{project_id}"
    
    if dry_run:
        return "simulated", f"Would delete project {project_id}", f"DELETE {url}", None # Deletion is destructive/hard to undo

    requests.delete(url, headers=headers).raise_for_status()
    logger.info(f"Deleted project: {project_id}")
    return "success", f"Deleted project {project_id}", f"DELETE {url}", None

@register_action('create_task')
def handle_create_task(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    url = "https://api.todoist.com/rest/v2/tasks"
    data = {k: v for k, v in action.items() if k not in ['type']}
    
    if dry_run:
        undo_action: Action = {"type": "delete_task", "id": "placeholder_id"}
        return "simulated", f"Would create task '{action.get('content')}'", f"POST {url} with {data}", undo_action

    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    task_id = resp.json().get('id')
    logger.info(f"Created task: {action.get('content')} ({task_id})")
    
    undo_action = {"type": "delete_task", "id": task_id}
    return "success", f"Created task {action.get('content')}", f"POST {url}", undo_action

@register_action('delete_task')
def handle_delete_task(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    # Internal action mostly for undo
    task_id = action.get('id')
    if not task_id:
         raise ValueError("Missing 'id' for delete_task")
    
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    
    if dry_run:
        return "simulated", f"Would delete task {task_id}", f"DELETE {url}", None

    requests.delete(url, headers=headers).raise_for_status()
    logger.info(f"Deleted task: {task_id}")
    return "success", f"Deleted task {task_id}", f"DELETE {url}", None

@register_action('create_label')
def handle_create_label(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    url = "https://api.todoist.com/rest/v2/labels"
    data = {"name": action.get('name')}
    
    if dry_run:
         undo_action: Action = {"type": "delete_label", "id": "placeholder_id"} # Todoist API doesn't fully document delete label by ID easily? actually it does
         return "simulated", f"Would create label '{action.get('name')}'", f"POST {url} with {data}", undo_action

    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    label_id = resp.json().get('id')
    logger.info(f"Created label: {action.get('name')}")
    
    # Todoist API for personal labels allows deletion by ID
    undo_action = {"type": "delete_label", "id": label_id}
    return "success", f"Created label {action.get('name')}", f"POST {url}", undo_action

@register_action('delete_label')
def handle_delete_label(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
     # Internal
    label_id = action.get('id')
    if not label_id:
         # Fallback to name if id not present (unlikely for undo flow)
         raise ValueError("Missing 'id' for delete_label")
    
    # Check if we should use name or ID. API uses ID for personal/shared labels usually.
    # documentation: DELETE https://api.todoist.com/rest/v2/labels/{id}
    
    url = f"https://api.todoist.com/rest/v2/labels/{label_id}"
    
    if dry_run:
        return "simulated", f"Would delete label {label_id}", f"DELETE {url}", None

    requests.delete(url, headers=headers).raise_for_status()
    logger.info(f"Deleted label: {label_id}")
    return "success", f"Deleted label {label_id}", f"DELETE {url}", None

@register_action('add_label')
def handle_add_label(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    """Adds a label to a task by appending to existing labels."""
    task_id = action.get('task_id')
    label = action.get('label')
    if not task_id or not label:
        raise ValueError("Missing 'task_id' or 'label' for add_label")
    
    get_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    update_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"

    undo_action: Action = {"type": "remove_label", "task_id": task_id, "label": label}

    if dry_run:
        return "simulated", f"Would add label '{label}' to task {task_id}", f"GET {get_url} -> POST {update_url}", undo_action

    # First fetch the task to get current labels
    task_resp = requests.get(get_url, headers=headers)
    task_resp.raise_for_status()
    current_labels = task_resp.json().get('labels', [])
    
    if label not in current_labels:
        current_labels.append(label)
        requests.post(update_url, headers=headers, json={'labels': current_labels}).raise_for_status()
        logger.info(f"Added label '{label}' to task {task_id}")
        return "success", f"Added label '{label}' to task {task_id}", f"POST {update_url}", undo_action
    else:
        logger.info(f"Label '{label}' already exists on task {task_id}")
        return "success", f"Label '{label}' already exists", f"GET {get_url}", None

@register_action('remove_label')
def handle_remove_label(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    """Removes a label from a task."""
    task_id = action.get('task_id')
    label = action.get('label')
    if not task_id or not label:
        raise ValueError("Missing 'task_id' or 'label' for remove_label")
    
    get_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    update_url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"

    undo_action: Action = {"type": "add_label", "task_id": task_id, "label": label}

    if dry_run:
        return "simulated", f"Would remove label '{label}' from task {task_id}", f"GET {get_url} -> POST {update_url}", undo_action

    # First fetch
    task_resp = requests.get(get_url, headers=headers)
    task_resp.raise_for_status()
    current_labels = task_resp.json().get('labels', [])
    
    if label in current_labels:
        current_labels.remove(label)
        requests.post(update_url, headers=headers, json={'labels': current_labels}).raise_for_status()
        logger.info(f"Removed label '{label}' from task {task_id}")
        return "success", f"Removed label '{label}' from task {task_id}", f"POST {update_url}", undo_action
    else:
        logger.info(f"Label '{label}' not found on task {task_id}")
        return "success", f"Label '{label}' not found", f"GET {get_url}", None

@register_action('create_section')
def handle_create_section(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    url = "https://api.todoist.com/rest/v2/sections"
    data = {
        "name": action.get('name'),
        "project_id": action.get('project_id')
    }
    
    if dry_run:
        undo_action = {"type": "delete_section", "id": "placeholder_id"}
        return "simulated", f"Would create section '{action.get('name')}'", f"POST {url} with {data}", undo_action

    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    section_id = resp.json().get('id')
    logger.info(f"Created section: {action.get('name')}")
    
    undo_action = {"type": "delete_section", "id": section_id}
    return "success", f"Created section {action.get('name')}", f"POST {url}", undo_action

@register_action('delete_section')
def handle_delete_section(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    # Internal
    section_id = action.get('id')
    if not section_id:
        raise ValueError("Missing 'id' for delete_section")
        
    url = f"https://api.todoist.com/rest/v2/sections/{section_id}"
    
    if dry_run:
        return "simulated", f"Would delete section {section_id}", f"DELETE {url}", None
        
    requests.delete(url, headers=headers).raise_for_status()
    logger.info(f"Deleted section: {section_id}")
    return "success", f"Deleted section {section_id}", f"DELETE {url}", None

@register_action('move_task')
def handle_move_task(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
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
        return "failed", "No destination provided", "", None

    # Undo for move is hard without previous state. Fetch state similarly to update_task
    undo_action: Optional[Action] = None
    if not dry_run:
        try:
            original_task = requests.get(url, headers=headers).json()
            undo_data = {}
            # We only need to revert project_id and section_id
            if 'project_id' in original_task:
                 undo_data['project_id'] = original_task['project_id']
            if 'section_id' in original_task:
                 undo_data['section_id'] = original_task['section_id']
            
            if undo_data:
                undo_action = {"type": "move_task", "id": task_id, **undo_data}
        except Exception:
            pass
            
    if dry_run:
         undo_action = {"type": "move_task", "id": task_id, "project_id": "original_id", "section_id": "original_id"}
         return "simulated", f"Would move task {task_id} to {data}", f"POST {url} with {data}", undo_action

    requests.post(url, headers=headers, json=data).raise_for_status()
    logger.info(f"Moved task {task_id}")
    return "success", f"Moved task {task_id}", f"POST {url}", undo_action

@register_action('add_comment')
def handle_add_comment(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
    url = "https://api.todoist.com/rest/v2/comments"
    data = {
        "task_id": action.get('task_id'),
        "content": action.get('content')
    }
    
    if dry_run:
         undo_action = {"type": "delete_comment", "id": "placeholder_id"}
         return "simulated", f"Would add comment to task {action.get('task_id')}", f"POST {url} with {data}", undo_action

    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    comment_id = resp.json().get('id')
    logger.info(f"Added comment to task {action.get('task_id')}")
    
    undo_action = {"type": "delete_comment", "id": comment_id}
    return "success", f"Added comment to task", f"POST {url}", undo_action

@register_action('delete_comment')
def handle_delete_comment(action: Action, headers: Dict[str, str], dry_run: bool = False) -> Tuple[str, str, str, Optional[Action]]:
     # Internal
    comment_id = action.get('id')
    if not comment_id:
        raise ValueError("Missing 'id' for delete_comment")
        
    url = f"https://api.todoist.com/rest/v2/comments/{comment_id}"
    
    if dry_run:
         return "simulated", f"Would delete comment {comment_id}", f"DELETE {url}", None
         
    requests.delete(url, headers=headers).raise_for_status()
    logger.info(f"Deleted comment: {comment_id}")
    return "success", f"Deleted comment {comment_id}", f"DELETE {url}", None


def execute_todoist_action(action: Action, api_token=TODOIST_API_TOKEN, dry_run=False) -> Tuple[str, str, str, Optional[Action]]:
    """
    Executes a single action using the registry.
    
    Returns a Tuple containing:
    1. Status (str): "success", "simulated", or "failed".
    2. Message (str): Human-readable result description.
    3. API Call (str): Description of the HTTP request (for debugging).
    4. Undo Action (Action/None): The inverse action to revert this change.
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
            return "failed", str(e), "", None
    else:
        logger.warning(f"Unknown action type: {action_type}")
        return "failed", f"Unknown action type {action_type}", "", None
