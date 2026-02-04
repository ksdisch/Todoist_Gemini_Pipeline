from typing import List, Dict, Any
from app.core.schemas import State, Action
from app.core.weekly_review.models import ReviewSession, Issue
from app.core.profile import Profile

class ActiveHonestyStep:
    def compute(self, state: State, session: ReviewSession, profile: Profile) -> Dict[str, Any]:
        active_name = profile.section_names.active
        # Find active section IDs
        active_section_ids = {s['id'] for s in state.sections if s['name'] == active_name}
        
        active_tasks = [t for t in state.tasks if t.get('section_id') in active_section_ids and not t.get('is_completed')]
        
        # Group by project
        by_project = {}
        for t in active_tasks:
            pid = t.get('project_id')
            if pid not in by_project:
                by_project[pid] = []
            by_project[pid].append(t)
            
        return {
            "total_active": len(active_tasks),
            "by_project": by_project,
            "tasks": active_tasks
        }

    def validate(self, state: State, session: ReviewSession, profile: Profile, user_inputs: Dict[str, Any]) -> List[Issue]:
        data = self.compute(state, session, profile)
        issues = []
        
        # Rule: Too many active tasks per project (e.g., > 5)
        # This constant could be in profile but hardcoding or using a reasonable default for now
        MAX_ACTIVE_PER_PROJECT = 5 
        
        for pid, tasks in data["by_project"].items():
            if len(tasks) > MAX_ACTIVE_PER_PROJECT:
                # Get project name
                proj = next((p for p in state.projects if p['id'] == pid), None)
                pname = proj['name'] if proj else "Unknown Project"
                
                issues.append(Issue(
                    id=f"too_many_active_{pid}",
                    title=f"Too many active tasks in {pname}",
                    description=f"You have {len(tasks)} active tasks in {pname}. Limit is {MAX_ACTIVE_PER_PROJECT}.",
                    severity="medium",
                    related_task_id=None
                ))
        
        # Rule: Vague tasks (short content)
        for t in data["tasks"]:
            content = t.get("content", "")
            if len(content.split()) < 3: # Fewer than 3 words might be vague
                 issues.append(Issue(
                    id=f"vague_task_{t['id']}",
                    title="Potentially Vague Task",
                    description=f"Task '{content}' seems vague. Make it actionable.",
                    severity="low",
                    related_task_id=t['id']
                ))
        
        return issues


    def recommend_actions(self, state: State, session: ReviewSession, profile: Profile, user_inputs: Dict[str, Any]) -> List[Action]:
        return []
