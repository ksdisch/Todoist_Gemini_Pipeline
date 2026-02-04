from typing import List, Dict, Any
from app.core.schemas import State, Action
from app.core.weekly_review.models import ReviewSession, Issue
from app.core.profile import Profile

class WaitingForStep:
    def compute(self, state: State, session: ReviewSession, profile: Profile) -> Dict[str, Any]:
        waiting_label = profile.waiting_label
        waiting_tasks = [
            t for t in state.tasks 
            if waiting_label in t.get("labels", []) and not t.get("is_completed")
        ]
        
        return {
            "count": len(waiting_tasks),
            "tasks": waiting_tasks
        }

    def validate(self, state: State, session: ReviewSession, profile: Profile, user_inputs: Dict[str, Any]) -> List[Issue]:
        data = self.compute(state, session, profile)
        issues = []
        
        for t in data["tasks"]:
            content = t.get("content", "").lower()
            description = t.get("description", "").lower()
            
            # Check for "waiting on" or "waiting for" in content or description
            has_metadata = (
                "waiting on" in content or 
                "waiting for" in content or 
                "waiting on" in description or 
                "waiting for" in description or
                len(description) > 5 # Assuming description usually holds the context
            )
            
            if not has_metadata:
                issues.append(Issue(
                    id=f"missing_waiting_metadata_{t['id']}",
                    title="Missing Waiting Context",
                    description=f"Task '{t.get('content')}' is marked Waiting but doesn't specify who/what you are waiting on.",
                    severity="medium",
                    related_task_id=t['id']
                ))
                
        return issues

    def recommend_actions(self, state: State, session: ReviewSession, profile: Profile, user_inputs: Dict[str, Any]) -> List[Action]:
        return []
