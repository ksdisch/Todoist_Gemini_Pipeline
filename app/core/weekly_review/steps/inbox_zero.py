from typing import List, Dict, Any
from app.core.schemas import State, Action
from app.core.weekly_review.models import ReviewSession, Issue
from app.core.profile import Profile

class InboxZeroStep:
    def compute(self, state: State, session: ReviewSession, profile: Profile) -> Dict[str, Any]:
        inbox_project_id = self._get_inbox_project_id(state)
        if not inbox_project_id:
            return {"count": 0, "tasks": []}
            
        inbox_tasks = [
            t for t in state.tasks 
            if t.get("project_id") == inbox_project_id and not t.get("is_completed")
        ]
        
        return {
            "count": len(inbox_tasks),
            "tasks": inbox_tasks
        }

    def validate(self, state: State, session: ReviewSession, profile: Profile, user_inputs: Dict[str, Any]) -> List[Issue]:
        data = self.compute(state, session, profile)
        if data["count"] > 0:
            return [Issue(
                id="inbox_not_empty",
                title="Inbox Not Empty",
                description=f"You still have {data['count']} items in your Inbox.",
                severity="high"
            )]
        return []

    def recommend_actions(self, state: State, session: ReviewSession, profile: Profile, user_inputs: Dict[str, Any]) -> List[Action]:
        return []

    def _get_inbox_project_id(self, state: State) -> str:
        # Try to find project with is_inbox_project = True (if available in schema) or name "Inbox"
        for p in state.projects:
            if p.get("is_inbox_project"):
                return p["id"]
        for p in state.projects:
            if p.get("name") == "Inbox":
                return p["id"]
        return ""
