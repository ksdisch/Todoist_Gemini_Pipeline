import google.generativeai as genai
from src.config import TODOIST_API_TOKEN, GEMINI_API_KEY
from src.client import get_tasks, get_projects
from src.actions import execute_todoist_action
from src.utils import format_state_for_ai
from src.parser import parse_and_validate_response
from src.logger import setup_logger

logger = setup_logger("Architect")

if not TODOIST_API_TOKEN or not GEMINI_API_KEY:
    logger.critical("Missing API keys in .env file. Exiting.")
    exit(1)

# Model setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

def execute_todoist_build(actions):
    """Executes a list of actions proposed by AI."""
    logger.info(f"Executing {len(actions)} actions...")
    for action in actions:
        execute_todoist_action(action, TODOIST_API_TOKEN)

def run_architect():
    """Main interactive loop for the Architect."""
    logger.info("Connecting to Todoist ...")
    tasks = get_tasks()
    projects = get_projects()
    
    state_description = format_state_for_ai(tasks, projects)
    
    system_prompt = """
    You are the Todoist Architect, an advanced productivity assistant.
    Your goal is to help the user organize their life by analyzing their tasks and executing changes to their Todoist.
    
    When you propose changes, you MUST output a JSON object in this specific format ONLY:
    
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
    
    logger.info("Correctly connected! The Architect is ready.")
    print("Type your request (or 'exit' to quit):")
    
    while True:
        user_input = input("\n> ")
        if user_input.lower() in ['exit', 'quit']:
            break
            
        print("🤖 Architect is thinking...")
        try:
            response = chat_session.send_message(user_input)
            text_response = response.text
            
            # Attempt to parse
            ai_data = parse_and_validate_response(text_response)

            if not ai_data:
                logger.warning("Malformed response. Retrying once...")
                retry_msg = "Your previous response violated the JSON schema. Respond ONLY with valid JSON."
                response = chat_session.send_message(retry_msg)
                text_response = response.text
                ai_data = parse_and_validate_response(text_response)

            if not ai_data:
                logger.error("Could not parse JSON. Falling back to advice-only mode.")
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
                    logger.info("Refreshing state from Todoist...")
                    tasks = get_tasks()
                    projects = get_projects()
                    new_state = format_state_for_ai(tasks, projects)

                    # Update AI context
                    logger.info("Syncing new state with Architect...")
                    update_msg = f"SYSTEM UPDATE: The actions have been executed. Here is the new state of tasks and projects:\n{new_state}\n\nPlease proceed with this new state."
                    chat_session.send_message(update_msg)

                    print("\n✨ Done! Ready for next command.")
                else:
                    print("Cancelled.")
                
        except Exception as e:
            logger.error(f"Error: {e}")

if __name__ == "__main__":
    run_architect()
