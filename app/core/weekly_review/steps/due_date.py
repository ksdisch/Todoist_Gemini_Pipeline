from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from app.core.schemas import State, Action
from app.core.weekly_review.models import ReviewSession, Issue
from app.core.profile import Profile

class DueDateIntegrityStep:
    def compute(self, state: State, session: ReviewSession, profile: Profile) -> Dict[str, Any]:
        tasks_with_due = [
            t for t in state.tasks 
            if t.get("due") and not t.get("is_completed")
        ]
        
        # Group by date string (YYYY-MM-DD)
        by_date = defaultdict(list)
        for t in tasks_with_due:
            d = t.get("due", {}).get("date")
            if d:
                by_date[d].append(t)
                
        return {
            "total_due": len(tasks_with_due),
            "by_date": dict(by_date),
            "tasks": tasks_with_due
        }

    def validate(self, state: State, session: ReviewSession, profile: Profile, user_inputs: Dict[str, Any]) -> List[Issue]:
        data = self.compute(state, session, profile)
        issues = []
        today = datetime.now().date()
        
        # Rule 1: Bulk undifferentiated due dates
        BULK_THRESHOLD = 5
        for date_str, tasks in data["by_date"].items():
            if len(tasks) > BULK_THRESHOLD:
                # Check if it's a real deadline day or just a dump
                # Heuristic: If all have same priority, likely a dump
                priorities = {t.get("priority") for t in tasks}
                if len(priorities) == 1:
                     issues.append(Issue(
                        id=f"bulk_due_{date_str}",
                        title=f"Bulk Due Date Detected ({date_str})",
                        description=f"You have {len(tasks)} tasks due on {date_str} with the same priority. Are these real deadlines?",
                        severity="medium"
                    ))
        
        # Rule 2: Far-future dates on low priority
        # Todoist: Priority 1 is low (default), 4 is high.
        FUTURE_THRESHOLD_DAYS = 30
        for t in data["tasks"]:
            due_str = t.get("due", {}).get("date")
            priority = t.get("priority", 1) 
            
            if due_str and priority == 1:
                try:
                    # Handle T-format sometimes? Todoist API usually returns YYYY-MM-DD
                    if "T" in due_str:
                        due_date = datetime.strptime(due_str.split("T")[0], "%Y-%m-%d").date()
                    else:
                        due_date = datetime.strptime(due_str, "%Y-%m-%d").date()
                    
                    if (due_date - today).days > FUTURE_THRESHOLD_DAYS:
                        issues.append(Issue(
                            id=f"fake_deadline_{t['id']}",
                            title="Suspicious Far-Future Deadline",
                            description=f"Task '{t.get('content')}' is low priority but due in >30 days. Use 'Someday' or 'Tickler' instead of a hard deadline?",
                            severity="low",
                            related_task_id=t['id']
                        ))
                except ValueError:
                    pass # Ignore parse errors
                    
        return issues

    def recommend_actions(self, state: State, session: ReviewSession, profile: Profile, user_inputs: Dict[str, Any]) -> List[Action]:
        return []
