from datetime import datetime
from typing import List
from app.core.schemas import State
from app.core.profile import Profile
from .models import Issue

def check_active_honesty(state: State, profile: Profile) -> List[Issue]:
    """
    Check for tasks that violate 'Active Honesty':
    - Overdue tasks
    """
    issues = []
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for task in state.tasks:
        due = task.get("due")
        if due and due.get("date"):
            if due["date"] < today_str:
                # Check if task is in an excluded project/section if we want to support exclusions here
                # consistently. For now, we apply global honesty.
                issues.append(Issue(
                    id=f"overdue_{task['id']}",
                    title=f"Overdue Task: {task['content']}",
                    description=f"Task was due on {due['date']}",
                    related_task_id=task['id'],
                    severity="high"
                ))
    
    return issues

def check_due_date_integrity(state: State, profile: Profile) -> List[Issue]:
    """
    Check for 'Due-Date Integrity'.
    """
    issues = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_count = 0
    
    for task in state.tasks:
        due = task.get("due")
        if due and due.get("date") == today_str:
            today_count += 1
            
    if today_count > 15: 
        issues.append(Issue(
            id="too_many_today",
            title="Overloaded Today",
            description=f"You have {today_count} tasks due today. Is this realistic?",
            severity="medium"
        ))
        
    return issues

def check_waiting_for_discipline(state: State, profile: Profile) -> List[Issue]:
    """
    Check for 'Waiting For' discipline using the profile's waiting label.
    """
    issues = []
    waiting_label = profile.waiting_label.lower()
    
    for task in state.tasks:
        content = task.get("content", "")
        labels = task.get("labels", []) # List of Label IDs usually, but maybe hydrated names?
        
        # We need to match label names. 
        # If 'labels' contains names (hydrated), we check that.
        # If 'labels' contains IDs, we can't easily check without a map.
        # As a fallback/heuristic, we check content for @LabelName style or just content text.
        
        is_waiting = False
        
        # 1. Check content text heuristic
        if waiting_label in content.lower():
            is_waiting = True
            
        # 2. TODO: Check actual label IDs if we have the mapping
            
        if is_waiting:
             if not task.get("due"):
                 issues.append(Issue(
                     id=f"waiting_no_date_{task['id']}",
                     title=f"Waiting task without date: {content}",
                     description=f"Tasks matching '{profile.waiting_label}' should have a follow-up date.",
                     related_task_id=task['id'],
                     severity="medium"
                 ))

    return issues
