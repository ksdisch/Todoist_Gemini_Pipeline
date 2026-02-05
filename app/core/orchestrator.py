from typing import List, Dict, Any, Optional

from app.core import todoist_client
from app.core.gemini_client import GeminiClient
from app.core.parser import parse_and_validate_response
from app.core.utils import format_state_for_ai
from app.core.schemas import AnalysisResult, Action, State
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# =================================================================================================
# TOUR HEADER: Orchestrator
# =================================================================================================
#
# WHAT THIS FILE DOES:
# This is the "Brain" of the application. It orchestrates the flow between the User, the AI (Gemini),
# and the System (Todoist). It does not perform low-level API calls itself (see todoist_client.py)
# nor does it parse strings (see parser.py). It manages the high-level loop:
# Fetch State -> Analyze (User Input) -> Propose Actions -> Execute -> Sync State.
#
# RESPONSIBILITIES:
# 1. State Management: Fetching current task state and formatting it for the AI.
# 2. Session Management: Maintaining the chat history and context window with Gemini.
# 3. Execution Control: Dispatching actions to the client and managing the "Undo" stack.
# 4. Error Recovery: Handling malformed AI responses with retry logic.
#
# KEY CONCEPTS:
# - State: Snapshot of tasks/projects. Passed to AI so it knows what exists.
# - Analysis: sending user intent + state to AI -> getting formatted JSON back.
# - Dry Run: The ability to simulate execution without side effects (passed down to client).
# - Undo Stack: A history of operations allowing the user to reverse the last batch.
#
# =================================================================================================

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
        """
        Fetches the latest live state from Todoist and prepares it for the AI.
        
        This is expensive (multiple API calls), so it should be called:
        1. At startup.
        2. Explicitly when the user hits 'Refresh'.
        3. Automatically after a batch of actions is executed (to keep the AI in sync).
        """
        logger.info("Fetching state from Todoist...")
        tasks = todoist_client.get_tasks()
        projects = todoist_client.get_projects()
        sections = todoist_client.get_sections()
        formatted = format_state_for_ai(tasks, projects)
        return State(tasks=tasks, projects=projects, sections=sections, formatted_context=formatted)

    def _initialize_chat(self, initial_state_context: str) -> None:
        """Initializes the chat session with the system prompt and initial state."""
        full_prompt = f"{SYSTEM_PROMPT}\n\nHere is the current state:\n{initial_state_context}"
        self.chat_session = self.gemini.start_chat(history=[
            {"role": "user", "parts": [full_prompt]}
        ])

    def analyze(self, state: State, user_message: str) -> AnalysisResult:
        """
        Sends the user's message to the AI and parses the response into structured actions.
        
        Contracts:
        - Inputs: Current application State, User's natural language string.
        - Outputs: AnalysisResult containing a 'thought' (str) and 'actions' (List[Action]).
        - Fail-safe: If JSON parsing fails twice, falls back to a text-only 'thought' with no actions.
        
        Thread Safety:
        - This is a blocking network call (Gemini API). MUST be run in a worker thread (see gui/workers.py).
        """
        if not self.chat_session:
            self._initialize_chat(state.formatted_context)
            # If we just started, the state is in history.
        
        logger.info("Analyzing user message...")
        response_text = self.gemini.send_message(user_message)
        
        ai_data = parse_and_validate_response(response_text)
        
        # WHY: We implement a single retry here because LLMs occasionally have "hiccups"
        # (formatting errors, markdown leakage) that are easily fixed by a stern reminder.
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
        """
        Executes a batch of actions against the Todoist API.
        
        Contracts:
        - Inputs: List of Action dictionaries.
        - Side Effects: 
            - Modifies real Todoist data (if dry_run=False).
            - Updates the internal _undo_stack.
        - Returns: Detailed results for each action, including success status and undo counterparts.
        
        Why Dry Run?
        - Allows the user to "Preview" destructive changes safely in the UI before committing.
        """
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
                     # WHY: Prepend to list. To undo [A, B, C], we must execute [UndoC, UndoB, UndoA].
                     # LIFO order is critical for dependent actions (e.g. create project -> create task in project).
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
            
        return results

    def get_undo_actions(self) -> List[Action]:
        """Returns the undo actions for the last executed batch, if any."""
        if not self._undo_stack:
            return []
        return self._undo_stack[-1]

    def perform_undo(self) -> List[Dict[str, Any]]:
        """
        Reverts the last batch of actions.
        
        Strategy:
        - Pops the last set of undo-actions from the stack.
        - Executes them immediately (no dry-run, no new undo stack generation).
        
        limitations:
        - This is "best effort". If external state changed (e.g. user deleted the task manually),
          these undo actions might fail.
        """
        if not self._undo_stack:
            return []
        
        actions_to_undo = self._undo_stack.pop()
        logger.info(f"Reverting {len(actions_to_undo)} actions...")
        
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
         """
         Updates the AI's internal context with the new System State.
         
         WHY THIS METHOD EXISTS:
         LLMs have a context window. Instead of restarting the session (losing chat history)
         or letting the AI 'hallucinate' the old state, we explicitly feed it the new state
         as a system update.
         
         Mechanism:
         - Sends a message representing the system, not the user.
         - Ignores the response (we don't need the AI to say "Received").
         """
         if self.chat_session:
             update_msg = f"SYSTEM UPDATE: The actions have been executed. Here is the new state of tasks and projects:\n{new_state.formatted_context}\n\nPlease proceed with this new state."
             try:
                 self.gemini.send_message(update_msg)
             except Exception:
                 pass
