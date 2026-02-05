import json
from typing import List, Dict, Any, Optional

from app.core import todoist_client
from app.core.schemas import State, Action, AnalysisResult
from app.core.orchestrator import Architect
from app.core.weekly_review import engine, planner, rules
from app.core.weekly_review.models import ReviewSession
from app.core.utils import format_task

def build_step_context(step_id: str, state: State, session: ReviewSession, profile: Any) -> str:
    """
    Constructs a focused context string for the specific step.
    This avoids sending the entire state to the LLM for every step.
    """
    lines = []
    
    if step_id == "clear_inbox":
        lines.append("CONTEXT: Inbox Processing")
        lines.append("Role: Help the user clear their Inbox. Suggest projects, labels, or immediate deletion.")
        
        # Filter for Inbox tasks
        inbox_project_id = None
        for p in state.projects:
            if p.is_inbox_project:
                inbox_project_id = p.id
                break
        
        inbox_tasks = [t for t in state.tasks if t.project_id == inbox_project_id]
        
        lines.append(f"\nThere are {len(inbox_tasks)} tasks in the Inbox:")
        for t in inbox_tasks:
            lines.append(format_task(t, state.projects))
            
    elif step_id == "active_honesty":
        lines.append("CONTEXT: Active Honesty & Clean-up")
        lines.append("Role: Help the user deal with overdue tasks and 'Waiting For' items. Be ruthless.")
        
        # Overdue
        overdue = rules.check_active_honesty(state, profile)
        lines.append(f"\nOverdue Tasks ({len(overdue)} items):")
        # specific logic to find the task objects for these issues would be better, 
        # but the Issue object doesn't carry full task data. 
        # Re-querying or efficient lookup is needed.
        # Simple approach: Check all tasks for overdue status again or ID match.
        
        # Let's iterate tasks once.
        overdue_tasks = [t for t in state.tasks if t.is_overdue] 
        # (Assuming is_overdue property exists or we compute it. Wrapper needed? 
        # todoist_api_python Task object doesn't have is_overdue? 
        # It has due dict. Let's assume standard due logic.)
        
        from app.core.weekly_review.rules import is_overdue
        
        overdue_tasks = [t for t in state.tasks if is_overdue(t)]
        
        for t in overdue_tasks:
             lines.append(format_task(t, state.projects))

        # Waiting For
        # We need the waiting label from profile
        waiting_label = profile.waiting_for_label if profile else "Waiting For"
        waiting_tasks = [t for t in state.tasks if waiting_label in t.labels]
        lines.append(f"\n'Waiting For' Tasks ({len(waiting_tasks)} items):")
        for t in waiting_tasks:
            lines.append(format_task(t, state.projects))

    elif step_id == "plan_next_week":
        lines.append("CONTEXT: Planning Next Week")
        lines.append("Role: Help the user select high-impact tasks. Suggest tasks that fill gaps in Area Coverage.")
        
        # Draft Info
        lines.append(f"\nCurrent Draft Focus Areas: {session.plan_draft.focus_areas}")
        lines.append(f"Current Draft Priorities: {session.plan_draft.top_priorities}")
        
        # Coverage Gaps?
        candidates = planner.build_candidates(state, profile)
        selected_ids = [t['id'] for t in session.plan_draft.selected_tasks]
        coverage = planner.compute_area_coverage(state, profile, candidates, selected_ids)
        
        lines.append("\nArea Coverage Status:")
        for c in coverage:
            lines.append(f"- {c.area_name}: {c.selected_count}/{c.required_min_touches} ({c.status})")
            
        # Candidates (Summarized?)
        # 50+ candidates might be too much. 
        # Let's show high priority ones not yet selected.
        lines.append("\nTop Candidates (Not yet selected):")
        unselected = [c for c in candidates if c['task'].id not in selected_ids]
        # Sort by priority
        unselected.sort(key=lambda x: x['task'].priority, reverse=True)
        
        for c in unselected[:15]: # Limit to top 15
            t = c['task']
            lines.append(format_task(t, state.projects) + f" [Rationale: {c['rationale']}]")

    else:
        lines.append(f"CONTEXT: Step {step_id}")
        lines.append("No specific filter logic defined for this step. Showing generic high-priority tasks.")
        top_tasks = sorted(state.tasks, key=lambda t: t.priority, reverse=True)[:10]
        for t in top_tasks:
            lines.append(format_task(t, state.projects))

    return "\n".join(lines)


def analyze_step(architect: Architect, step_id: str, state: State, session: ReviewSession, profile: Any, user_instruction: str = "") -> AnalysisResult:
    """
    Calls the Architect with step-specific context.
    """
    
    # 1. Build Context
    step_context = build_step_context(step_id, state, session, profile)
    
    # 2. Construct Prompt
    # We'll prepend the specific instructions to the user message
    prompt = f"""
    The user is performing a Weekly Review.
    Current Step: {step_id}
    
    {step_context}
    
    User Instruction: {user_instruction or 'Please review this situation and suggest actions.'}
    """
    
    # 3. Call Architect
    # We treat this as a single-turn analysis for now, 
    # but we reuse the architect's analyze method which manages chat session.
    # If we want a fresh session per step, we might need to reset or bypass.
    # For now, keeping history is fine (user might ask follow-up).
    
    # BUT: The Architect.analyze() usually injects the FULL state history if new.
    # We want to force *our* focused context.
    
    # Workaround: We can't easily replace the Architect's internal context management 
    # without changing Architect. 
    # The Architect initializes with State.formatted_context.
    # If we want to override that, we might need a dedicated method on Architect 
    # or just rely on the fact that we put the context in the message.
    
    # Let's pass the prompt as the user_message.
    # The Architect will append it to history.
    
    return architect.analyze(state, prompt)
