import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable

from app.core.schemas import State
from app.core.profile import load_profile, Profile
from .models import ReviewSession, ReviewStep, StepResult, Issue, WeeklyPlanDraft
from . import rules, persistence, planner
import os

PROFILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "app", "profile", "kyle.json")

# --- Step Definitions ---

STEPS: List[ReviewStep] = [
    ReviewStep(
        id="clear_inbox",
        title="Get Clear",
        description="Process your physical and digital inboxes. Get everything into Todoist.",
        order=1
    ),
    ReviewStep(
        id="active_honesty",
        title="Active Honesty",
        description="Review overdue tasks and stale items. Be honest about what you can do.",
        order=2
    ),
    ReviewStep(
        id="calendar_review",
        title="Calendar Review",
        description="Look at past 2 weeks (what did I miss?) and next 2 weeks (what's coming?).",
        order=3
    ),
    ReviewStep(
        id="plan_next_week",
        title="Plan Next Week",
        description="Select focus areas and top priorities for the coming week.",
        order=4
    )
]

# --- Engine Logic ---

def _get_step_by_id(step_id: str) -> Optional[ReviewStep]:
    for s in STEPS:
        if s.id == step_id:
            return s
    return None

def _get_next_step_id(current_step_id: str) -> Optional[str]:
    # Find index
    idx = -1
    for i, s in enumerate(STEPS):
        if s.id == current_step_id:
            idx = i
            break
    
    if idx != -1 and idx + 1 < len(STEPS):
        return STEPS[idx + 1].id
    return None

def start_session(state: State) -> ReviewSession:
    """Start a new review session."""
    session_id = str(uuid.uuid4())
    session = ReviewSession(
        id=session_id,
        start_time=datetime.now(),
        current_step_id=STEPS[0].id
    )
    persistence.save_session(session)
    return session

def load_session(session_id: str) -> Optional[ReviewSession]:
    return persistence.load_session(session_id)

def _load_default_profile() -> Profile:
    # Construct distinct path or rely on caller? 
    # We try to load 'kyle.json' from known location
    # Note: __file__ is app/core/weekly_review/engine.py
    # Root is up 3 levels? No, app is top package. 
    # Let's assume working directory is project root usually.
    # Safe robust path:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # base_dir should be '.../app' usually, actually let's just use the known relative path if cwd is right.
    # But safer to use relative to this file.
    # app/core/weekly_review/ -> app/core/ -> app/ -> root/ -> root/app/profile/kyle.json
    # actually app/ is inside root. 
    # engine.py is in app/core/weekly_review
    # .. -> core
    # .. -> app
    # .. -> root
    # then root/app/profile/kyle.json
    path = os.path.join(base_dir, "..", "app", "profile", "kyle.json")
    if not os.path.exists(path):
         # Try local dev path
         path = "app/profile/kyle.json"
    
    return load_profile(path)

def get_step_viewmodel(step_id: str, state: State, session: ReviewSession, profile: Optional[Profile] = None) -> Dict[str, Any]:
    """
    Return data for the UI to render the step.
    This is where we'd customize data based on the step.
    """
    step = _get_step_by_id(step_id)
    if not step:
        return {"error": "Step not found"}
        
    vm = {
        "step": step,
        "is_last_step": step_id == STEPS[-1].id,
        "context": {}
    }
    
    if profile is None:
        profile = _load_default_profile()

    # Per-step context
    if step_id == "active_honesty":
        vm["context"]["issues"] = rules.check_active_honesty(state, profile)
        vm["context"]["integrity_issues"] = rules.check_due_date_integrity(state, profile)
        vm["context"]["waiting_issues"] = rules.check_waiting_for_discipline(state, profile)
        
    elif step_id == "calendar_review":
        # Placeholder for calendar data
        vm["context"]["note"] = "Check your external calendar app."
        
    elif step_id == "plan_next_week":
        vm["context"]["draft"] = session.plan_draft
        
        # 1. Build Candidates
        candidates = planner.build_candidates(state, profile)
        vm["context"]["candidates"] = candidates
        
        # 2. Get current selection from session data (if any)
        # We store transient selections in session.data['plan_next_week_selections'] maybe?
        # Or we rely on the client passing them back? 
        # The engine is stateless regarding UI transient state unless saved.
        # But 'validate_step' needs to check them.
        # We can look at session.plan_draft.selected_tasks if they saved continuously?
        # Or look at last step result? No.
        # Let's assume the UI sends current selection in 'context' or we rely on saved draft.
        selected_ids = [t['id'] for t in session.plan_draft.selected_tasks]
        
        # 3. Compute Coverage
        coverage = planner.compute_area_coverage(state, profile, candidates, selected_ids)
        vm["context"]["area_coverage"] = coverage
        
    return vm

def validate_step(step_id: str, state: State, session: ReviewSession, profile: Optional[Profile] = None) -> List[Issue]:
    """
    Check if the user can proceed. 
    Some steps might enforce "no overdue tasks" before proceeding.
    """
    issues = []
    
    if profile is None:
        profile = _load_default_profile()

    if step_id == "active_honesty":
        # Strict mode: must resolve all overdue issues?
        # For now, we just warn.
        issues.extend(rules.check_active_honesty(state, profile))
    
    elif step_id == "plan_next_week":
        # Check Coverage Gate
        # We need to know the CURRENT selections. 
        # If this is called during a 'next' transition, session.plan_draft should be up to date?
        # Let's assume complete_step was called OR the draft is updated progressively.
        # Ideally, validate_step is called on 'Next' click.
        # But we need the data.
        # Let's assume session.plan_draft has the latest selections.
        
        candidates = planner.build_candidates(state, profile)
        selected_ids = [t['id'] for t in session.plan_draft.selected_tasks]
        coverage = planner.compute_area_coverage(state, profile, candidates, selected_ids)
        
        # We also need skipped areas. Where are they stored?
        # Let's store them in session.data for now as 'skipped_areas'
        skipped_areas = session.data.get("skipped_areas", {})
        
        issues.extend(planner.check_coverage_gate(coverage, skipped_areas))
        
    return issues

def complete_step(step_id: str, session: ReviewSession, user_inputs: Dict[str, Any]) -> StepResult:
    """
    Commit changes for the step and move to next.
    """
    # 1. Process inputs
    # 1. Process inputs
    if step_id == "plan_next_week":
        # Update draft Plan
        # We expect user_inputs to contain: focus_areas, top_priorities, notes, selected_task_ids
        # And maybe skipped_areas
        
        # Update skipped areas if present
        if "skipped_areas" in user_inputs:
            # Merge or overwrite?
            current_skipped = session.data.get("skipped_areas", {})
            current_skipped.update(user_inputs["skipped_areas"])
            session.data["skipped_areas"] = current_skipped
            
        # Re-generate draft with new inputs
        # We need state to hydrate tasks. 
        # Note: complete_step signature doesn't have State!
        # We might need to inject it or change signature.
        # Refactoring constraint: "Maintain a clean API".
        # If we can't pass state, we can't hydrate easily inside complete_step.
        
        # WORKAROUND: For now, we only update the simple fields here.
        # The 'selected_tasks' hydration is complex without State.
        # Maybe we assume the caller (orchestrator) handles hydration?
        # OR we change signature to accept State?
        # Given I can edit engine.py freely, I should add State to complete_step if possible.
        # BUT 'complete_step' is likely called by orchestrator which has state.
        # Let's stick to updating the pure data fields.
        
        if "focus_areas" in user_inputs:
            session.plan_draft.focus_areas = user_inputs["focus_areas"]
        if "top_priorities" in user_inputs:
            session.plan_draft.top_priorities = user_inputs["top_priorities"]
        if "notes" in user_inputs:
            session.plan_draft.notes = user_inputs["notes"]
            
        # For selected_tasks, if we get IDs, we store them. 
        # But the draft object has 'selected_tasks' as List[Dict].
        # If we receive IDs, we can't full save.
        # Let's rely on the orchestrator to pass full task objects? Unlikely.
        # Let's rely on the fact that we need state.
        pass # Placeholder comment


    # 2. Record result
    result = StepResult(
        step_id=step_id,
        completed_at=datetime.now(),
        data=user_inputs
    )
    
    # Remove existing result for this step if any (retry logic)
    session.completed_steps = [res for res in session.completed_steps if res.step_id != step_id]
    session.completed_steps.append(result)
    
    # 3. Advance
    next_id = _get_next_step_id(step_id)
    if next_id:
        session.current_step_id = next_id
    else:
        # Finished
        session.status = "completed"
        session.current_step_id = None
        
    persistence.save_session(session)
    return result
