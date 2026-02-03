import requests
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
import ai_response_parser

# Load environment variables
load_dotenv()

# ================= CONFIGURATION =================
TODOIST_API_TOKEN = os.getenv("TODOIST_API_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TODOIST_API_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Missing API keys in .env file")

# Model setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

# ================= TODOIST CLIENT =================

def get_tasks():
    """Fetches active tasks from Todoist."""
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {"Authorization": f"Bearer {TODOIST_API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching tasks: {e}")
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
        print(f"Error fetching projects: {e}")
        return []

# ================= ACTION HANDLERS =================

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
    print(f"✅ Closed task: {task_id}")

@register_action('update_task')
def handle_update_task(action, headers):
    task_id = action.get('id')
    if not task_id:
        raise ValueError("Missing 'id' for update_task")
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    data = {k: v for k, v in action.items() if k not in ['type', 'id']}
    requests.post(url, headers=headers, json=data).raise_for_status()
    print(f"✅ Updated task: {task_id}")

@register_action('create_project')
def handle_create_project(action, headers):
    url = "https://api.todoist.com/rest/v2/projects"
    data = {"name": action.get('name')}
    requests.post(url, headers=headers, json=data).raise_for_status()
    print(f"✅ Created project: {action.get('name')}")

@register_action('create_task')
def handle_create_task(action, headers):
    url = "https://api.todoist.com/rest/v2/tasks"
    data = {k: v for k, v in action.items() if k not in ['type']}
    requests.post(url, headers=headers, json=data).raise_for_status()
    print(f"✅ Created task: {action.get('content')}")

@register_action('create_label')
def handle_create_label(action, headers):
    url = "https://api.todoist.com/rest/v2/labels"
    data = {"name": action.get('name')}
    requests.post(url, headers=headers, json=data).raise_for_status()
    print(f"✅ Created label: {action.get('name')}")

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
        print(f"✅ Added label '{label}' to task {task_id}")
    else:
        print(f"ℹ️ Label '{label}' already exists on task {task_id}")

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
        print(f"✅ Removed label '{label}' from task {task_id}")
    else:
        print(f"ℹ️ Label '{label}' not found on task {task_id}")

@register_action('create_section')
def handle_create_section(action, headers):
    url = "https://api.todoist.com/rest/v2/sections"
    data = {
        "name": action.get('name'),
        "project_id": action.get('project_id')
    }
    requests.post(url, headers=headers, json=data).raise_for_status()
    print(f"✅ Created section: {action.get('name')}")

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
        print("⚠️ No destination provided for move_task")
        return

    # Use the close endpoint? No, move has its own handling often, but standard update works for project_id.
    # Actually, Todoist REST API uses 'project_id' and 'section_id' in the standard update endpoint for moving?
    # No, strictly speaking: "To move a task to a different project... use the update task endpoint."
    # Wait, 'section_id' can also be updated via standard update.
    # So we can just reuse the update endpoint effectively, but keeping it as a semantic action is good for the AI.
    
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    requests.post(url, headers=headers, json=data).raise_for_status()
    print(f"✅ Moved task {task_id} " + (f"to project {project_id} " if project_id else "") + (f"to section {section_id}" if section_id else ""))

@register_action('add_comment')
def handle_add_comment(action, headers):
    url = "https://api.todoist.com/rest/v2/comments"
    data = {
        "task_id": action.get('task_id'),
        "content": action.get('content')
    }
    requests.post(url, headers=headers, json=data).raise_for_status()
    print(f"✅ Added comment to task {action.get('task_id')}")

def execute_todoist_action(action):
    """Executes a single action using the registry."""
    headers = {
        "Authorization": f"Bearer {TODOIST_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    action_type = action.get('type')
    handler = ACTION_REGISTRY.get(action_type)
    
    if handler:
        try:
            handler(action, headers)
        except Exception as e:
            print(f"❌ Error executing {action_type}: {e}")
    else:
        print(f"⚠️ Unknown action type: {action_type}")

def execute_todoist_build(actions):
    """Executes a list of actions proposed by AI."""
    print(f"\n🚀 Executing {len(actions)} actions...")
    for action in actions:
        execute_todoist_action(action)

# ================= ARCHITECT ANALYST =================

def format_state_for_ai(tasks, projects):
    """Formats current state for the AI context."""
    task_lines = []
    for t in tasks:
        task_lines.append(f"ID: {t['id']} | Content: {t['content']} | Priority: {t['priority']} | Due: {(t.get('due') or {}).get('string', 'None')}")
    
    project_lines = []
    for p in projects:
        project_lines.append(f"ID: {p['id']} | Name: {p['name']}")
        
    return f"""
Current Projects:
{chr(10).join(project_lines)}

Current Tasks:
{chr(10).join(task_lines)}
"""

def run_architect():
    """Main interactive loop for the Architect."""
    print("... Connecting to Todoist ...")
    tasks = get_tasks()
    projects = get_projects()
    
    state_description = format_state_for_ai(tasks, projects)
    
    chat_history = []
    
    system_prompt = """
    You are the Todoist Architect, an advanced productivity assistant.
    Your goal is to help the user organize their life by analyzing their tasks and executing changes to their Todoist.
    
    When you propose changes, you MUST output a JSON object in this specific format ONLY (do not wrap in markdown code blocks if possible, or keep it clean):
    
    {
        "thought": "Your reasoning here...",
        "actions": [
            {"type": "create_project", "name": "New Project Name"},
            {"type": "update_task", "id": "task_id", "content": "New Name", "priority": 4},
            {"type": "close_task", "id": "task_id"},
            {"type": "create_task", "content": "Task Name", "project_id": "optional_id", "due_string": "tomorrow", "labels": ["label1"]},
            {"type": "create_label", "name": "Label Name"},
            {"type": "add_label", "task_id": "task_id", "label": "Label Name"},
            {"type": "remove_label", "task_id": "task_id", "label": "Label Name"},
            {"type": "create_section", "name": "Section Name", "project_id": "project_id"},
            {"type": "move_task", "id": "task_id", "project_id": "optional_p_id", "section_id": "optional_s_id"},
            {"type": "add_comment", "task_id": "task_id", "content": "Comment content"}
        ]
    }
    
    If you just want to talk or give advice without actions, return:
    {
        "thought": "Your advice...",
        "actions": []
    }
    """
    
    chat_session = model.start_chat(history=[
        {"role": "user", "parts": [system_prompt + "\n\nHere is the current state:\n" + state_description]}
    ])
    
    print("\nCorrectly connected! The Architect is ready.")
    print("Type your request (or 'exit' to quit):")
    
    while True:
        user_input = input("\n> ")
        if user_input.lower() in ['exit', 'quit']:
            break
            
        print("🤖 Architect is thinking...")
        try:
            response = chat_session.send_message(user_input)
            text_response = response.text
            
            # Attempt to parse JSON with robust strategy
            ai_data = ai_response_parser.parse_and_validate_response(text_response)

            if not ai_data:
                print("⚠️ Malformed response. Retrying once...")
                retry_msg = "Your previous response violated the JSON schema. Respond ONLY with valid JSON."
                response = chat_session.send_message(retry_msg)
                text_response = response.text
                ai_data = ai_response_parser.parse_and_validate_response(text_response)

            if not ai_data:
                # Fallback to advice-only mode
                print("⚠️ Could not parse JSON. Falling back to advice-only mode.")
                ai_data = {
                    "thought": text_response,
                    "actions": []
                }

            print(f"\n🧠 Analysis: {ai_data.get('thought')}")
            
            actions = ai_data.get('actions', [])
            if actions:
                print(f"\n⚠️ Proposed {len(actions)} actions:")
                for i, action in enumerate(actions, 1):
                    print(f"{i}. {action['type']}: {action.get('content') or action.get('name') or action.get('id')}")
                    
                confirm = input("\nExecute these changes? (y/n): ")
                if confirm.lower() == 'y':
                    execute_todoist_build(actions)

                    # Refresh state
                    print("🔄 Refreshing state from Todoist...")
                    tasks = get_tasks()
                    projects = get_projects()
                    new_state = format_state_for_ai(tasks, projects)

                    # Update AI context
                    print("🧠 Syncing new state with Architect...")
                    update_msg = f"SYSTEM UPDATE: The actions have been executed. Here is the new state of tasks and projects:\n{new_state}\n\nPlease proceed with this new state."
                    chat_session.send_message(update_msg)

                    print("\n✨ Done! Ready for next command.")
                else:
                    print("Cancelled.")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_architect()
