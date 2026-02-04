from typing import List, Dict, Any, Optional

from app.core import todoist_client
from app.core.gemini_client import GeminiClient
from app.core.parser import parse_and_validate_response
from app.core.utils import format_state_for_ai
from app.core.schemas import AnalysisResult, Action, State
from app.core.logger import setup_logger

logger = setup_logger(__name__)

SYSTEM_PROMPT = """
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

class Architect:
    def __init__(self):
        self.gemini = GeminiClient()
        self.chat_session = None
        self._undo_stack: List[List[Action]] = [] # Stack of undo actions for each batch

    def fetch_state(self) -> State:
        """Fetches tasks and projects, formats them for AI."""
        logger.info("Fetching state from Todoist...")
        tasks = todoist_client.get_tasks()
        projects = todoist_client.get_projects()
        formatted = format_state_for_ai(tasks, projects)
        return State(tasks=tasks, projects=projects, formatted_context=formatted)

    def _initialize_chat(self, initial_state_context: str) -> None:
        """Initializes the chat session with the system prompt and initial state."""
        full_prompt = f"{SYSTEM_PROMPT}\n\nHere is the current state:\n{initial_state_context}"
        self.chat_session = self.gemini.start_chat(history=[
            {"role": "user", "parts": [full_prompt]}
        ])

    def analyze(self, state: State, user_message: str) -> AnalysisResult:
        """
        Analyzes the user message given the current state.
        If chat session is not active, starts one.
        """
        if not self.chat_session:
            self._initialize_chat(state.formatted_context)
            # If we just started, the state is in history.
            # But if this is a subsequent call (though chat_session should be persistent if object is),
            # we generally just send the user message. 
            # However, original code implies we might send state updates?
            # Original code: sends update_msg after execution.
        
        logger.info("Analyzing user message...")
        response_text = self.gemini.send_message(user_message)
        
        ai_data = parse_and_validate_response(response_text)
        
        if not ai_data:
            logger.warning("Malformed response. Retrying once...")
            retry_msg = "Your previous response violated the JSON schema. Respond ONLY with valid JSON."
            response_text = self.gemini.send_message(retry_msg)
            ai_data = parse_and_validate_response(response_text)
            
        if not ai_data:
             logger.error("Could not parse JSON. Falling back to advice-only mode.")
             return {
                 "thought": response_text or "Error: No response or invalid JSON.",
                 "actions": []
             }
             
        # Normalize keys if needed
        return {
            "thought": ai_data.get("thought", ""),
            "actions": ai_data.get("actions", [])
        }

    def execute(self, actions: List[Action], dry_run: bool = False) -> List[Dict[str, Any]]:
        """Executes the list of actions."""
        results = []
        batch_undo_actions = []
        
        logger.info(f"{'Simulating' if dry_run else 'Executing'} {len(actions)} actions...")
        
        for action in actions:
            status, msg, api_call, undo_action = todoist_client.execute_todoist_action(action, dry_run=dry_run)
            
            # Map status to boolean success for backward compatibility
            # "simulated" is considered a successful execution of the dry run
            is_success = status in ("success", "simulated")
            
            if is_success:
                 if undo_action:
                     # Prepend to reverse order of operations later
                     batch_undo_actions.insert(0, undo_action)
            
            results.append({
                "action": action,
                "status": status,
                "message": msg,
                "api_call": api_call,
                "success": is_success,
                "undo_action": undo_action 
            })
        
        if not dry_run and batch_undo_actions:
            self._undo_stack.append(batch_undo_actions)
            # Limit stack size if needed, but for now keep it simple
            
        return results

    def get_undo_actions(self) -> List[Action]:
        """Returns the undo actions for the last executed batch, if any."""
        if not self._undo_stack:
            return []
        return self._undo_stack[-1]

    def perform_undo(self) -> List[Dict[str, Any]]:
        """Executes the undo actions for the last batch."""
        if not self._undo_stack:
            return []
        
        actions_to_undo = self._undo_stack.pop()
        logger.info(f"Reverting {len(actions_to_undo)} actions...")
        
        # We don't want to add undo actions for undo actions, so we might need a flag
        # Or simply call execute but don't add to stack if it's an undo (handled by caller typically)
        # But here we are inside orchestrator.
        # Let's just execute them directly via todoist_client to avoid recursive stack addition
        
        results = []
        for action in actions_to_undo:
             # dry_run=False because we ARE undoing associated real changes
             status, msg, api_call, _ = todoist_client.execute_todoist_action(action, dry_run=False)
             is_success = status == "success"
             results.append({
                "action": action,
                "status": status,
                "message": msg,
                "api_call": api_call,
                "success": is_success
            })
            
        return results

    def sync_state(self, new_state: State) -> None:
         """Updates the AI context with the new state after execution."""
         if self.chat_session:
             update_msg = f"SYSTEM UPDATE: The actions have been executed. Here is the new state of tasks and projects:\n{new_state.formatted_context}\n\nPlease proceed with this new state."
             # We send this message essentially as a hidden system/user update
             # We don't necessarily read the response here, or we treat it as acknowledgement.
             # Original code: sends message, ignores response essentially (just waits for next user input).
             try:
                 self.gemini.send_message(update_msg)
             except Exception:
                 pass
