from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.core.schemas import State
from .models import Issue

def check_active_honesty(state: State) -> List[Issue]:
    """
    Check for tasks that violate 'Active Honesty':
    - Overdue tasks (past due date)
    - Tasks with no due date (optional, depending on system, but usually good to flag)
    - Stale tasks (created long ago, no updates - hard to track without history, 
      so we'll focus on overdue for now)
    """
    issues = []
    
    # Simple check for overdue
    # Note: Todoist API usually returns 'due' object with 'date' string YYYY-MM-DD
    # We'll need to parse it. 
    # For now, we assume the 'state' object has tasks with 'due' field.
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for task in state.tasks:
        due = task.get("due")
        if due and due.get("date"):
            if due["date"] < today_str:
                issues.append(Issue(
                    id=f"overdue_{task['id']}",
                    title=f"Overdue Task: {task['content']}",
                    description=f"Task was due on {due['date']}",
                    related_task_id=task['id'],
                    severity="high"
                ))
    
    return issues

def check_due_date_integrity(state: State) -> List[Issue]:
    """
    Check for 'Due-Date Integrity'.
    This is harder to check programmatically without knowing user intent,
    but we can flag:
    - Tasks with due dates very far in the future (might be fake)
    - A massive pile-up of tasks due 'Today' (impossible to finish)
    """
    issues = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_count = 0
    
    for task in state.tasks:
        due = task.get("due")
        if due and due.get("date") == today_str:
            today_count += 1
            
    if today_count > 15: # Arbitrary threshold for "too many"
        issues.append(Issue(
            id="too_many_today",
            title="Overloaded Today",
            description=f"You have {today_count} tasks due today. Is this realistic?",
            severity="medium"
        ))
        
    return issues

def check_waiting_for_discipline(state: State) -> List[Issue]:
    """
    Check for 'Waiting For' discipline.
    - Tasks with 'Waiting For' label (or similar) that are old or have no due date/reminder.
    """
    issues = []
    # Identify 'waiting for' label ID or name. 
    # Since we might not have the ID mapping easily, we look for 'Waiting' in label names if possible,
    # or rely on the state having hydrated labels.
    # For this implementation, we'll search for a label named 'Waiting For' or 'waiting_for' in the task labels.
    
    # We might need to iterate projects/labels to find the ID first, but let's assume `labels` 
    # in task is a list of strings (names) or we check against known IDs if available.
    # The `State` object usually has raw API response, so `labels` are often IDs.
    
    # Let's try to find the label ID for "Waiting For"
    waiting_label_id = None
    # We don't have direct access to labels list in State dataclass based on schemas.py viewed earlier,
    # but `state.projects` is there. Labels might be fetched but not explicitly in State dataclass?
    # View schemas.py again showed: tasks, projects, formatted_context. 
    # Usually labels are separate. If they are missing from State, we might only scan content or rely on existing labels.
    
    # Constraint: "Use existing State/Action schemas". 
    # If State doesn't have labels list, we can't easily map ID->Name.
    # We will assume for now we look for tasks with content starting with "Waiting For" 
    # or if we add labels to State later. 
    # Let's look for "@Waiting" in content or just check if `labels` (ids) field is present and non-empty,
    # but we can't be specific without label map. 
    # Actually, let's assume the user uses a "Waiting For" project or section if labels aren't available?
    # Or just skip specific label check and look for keywords.
    
    keyword = "Waiting For"
    
    for task in state.tasks:
        content = task.get("content", "")
        # Check if parsed labels names are attached? Todoist API `tasks` have `labels` (list of IDs).
        # We'll just check content for now as a heuristic.
        
        if keyword.lower() in content.lower():
             # Logic: Waiting for tasks should have a follow-up date (due date).
             if not task.get("due"):
                 issues.append(Issue(
                     id=f"waiting_no_date_{task['id']}",
                     title=f"Waiting task without date: {content}",
                     description="Waiting tasks should have a follow-up date.",
                     related_task_id=task['id'],
                     severity="medium"
                 ))

    return issues
