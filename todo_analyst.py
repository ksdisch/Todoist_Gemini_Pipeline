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

def execute_todoist_action(action):
    """Executes a single action on Todoist API."""
    headers = {
        "Authorization": f"Bearer {TODOIST_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    action_type = action.get('type')
    
    try:
        if action_type == 'close_task':
            task_id = action.get('id')
            url = f"https://api.todoist.com/rest/v2/tasks/{task_id}/close"
            requests.post(url, headers=headers).raise_for_status()
            print(f"✅ Closed task: {task_id}")
            
        elif action_type == 'update_task':
            task_id = action.get('id')
            url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
            data = {k: v for k, v in action.items() if k not in ['type', 'id']}
            requests.post(url, headers=headers, json=data).raise_for_status()
            print(f"✅ Updated task: {task_id}")
            
        elif action_type == 'create_project':
            url = "https://api.todoist.com/rest/v2/projects"
            data = {"name": action.get('name')}
            requests.post(url, headers=headers, json=data).raise_for_status()
            print(f"✅ Created project: {action.get('name')}")
            
        elif action_type == 'create_task':
            url = "https://api.todoist.com/rest/v2/tasks"
            data = {k: v for k, v in action.items() if k not in ['type']}
            requests.post(url, headers=headers, json=data).raise_for_status()
            print(f"✅ Created task: {action.get('content')}")
            
        else:
            print(f"⚠️ Unknown action type: {action_type}")
            
    except Exception as e:
        print(f"❌ Error executing {action_type}: {e}")

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
            {"type": "create_task", "content": "Task Name", "project_id": "optional_id", "due_string": "tomorrow"}
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
                    print("\n✨ Done! Ready for next command.")
                else:
                    print("Cancelled.")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_architect()
