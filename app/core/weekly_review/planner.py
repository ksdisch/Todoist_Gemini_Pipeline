from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from app.core.schemas import State, Action
from app.core.profile import Profile
from app.core.weekly_review.models import AreaCoverage, Issue, WeeklyPlanDraft

# =================================================================================================
# TOUR HEADER: Weekly Planner Logic
# =================================================================================================
#
# JOB: 
# This module contains the "intelligence" for the "Plan Next Week" step. It determines what tasks
# should be suggested to the user and checks if the plan is balanced.
#
# KEY CONCEPTS:
# 1. Candidate Selection: We don't show ALL tasks. We filter for "high signal" tasks (Overdue, High Priority).
# 2. Area Coverage: We check if the user is neglecting any life areas defined in their profile.
# 3. Coverage Gate: We prevent the user from finishing the weekly review if they have "Missing" coverage
#    without a valid excuse (skipped area).
#
# =================================================================================================

def build_candidates(state: State, profile: Profile) -> List[Dict[str, Any]]:
    """
    Selects tasks that are worthy of being on the Weekly Plan.
    
    CRITERIA (Why these?):
    1. Overdue/Due Soon: Immediate urgency.
    2. Priority >= P2 (Red/Orange): User explicitly flagged these as important.
    3. Inbox: Unprocessed items that might need scheduling.
    
    Returns a list of task objects with an added 'planner_reasons' field (e.g. ['overdue', 'high_priority']).
    """
    candidates = []
    today = datetime.now().date()
    
    # Priority mapping: Todoist API p4=Priority 1 (Red), p1=Priority 4 (Grey)
    # We want "Priority >= 3" in Todoist terms? Or API terms?
    # User said "priority >= 3", usually implies High/Medium (Red/Orange).
    # In API: 4=Red, 3=Orange, 2=Blue, 1=Grey.
    # So we want API priority >= 3 (Red/Orange).
    
    for task in state.tasks:
        is_candidate = False
        reasons = []

        # 1. Overdue / Due Soon
        if task.get("due") and task["due"].get("date"):
            try:
                due_date_str = task["due"]["date"]
                # Handle potential datetime strings if present, though typically YYYY-MM-DD
                if "T" in due_date_str:
                     due_date_str = due_date_str.split("T")[0]
                
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                days_diff = (due_date - today).days
                
                if days_diff < 0:
                    is_candidate = True
                    reasons.append("overdue")
                elif days_diff <= 7:
                    is_candidate = True
                    reasons.append("due_soon")
            except ValueError:
                pass # safe fail

        # 2. High Priority (Red/Orange)
        # API: 4 is highest.
        prio = task.get("priority", 1)
        if prio >= 3:
            is_candidate = True
            reasons.append("high_priority")

        # 3. Inbox
        # Check against Profile if we had inbox project name, or default "Inbox"
        # Since State usually has 'projects', we can look up project name by id if needed.
        # But State.tasks items should have project_id. 
        # We need to map project_id to name to check "Inbox".
        # State.projects is a list of dicts.
        project_name = _get_project_name(task.get("project_id"), state.projects)
        if project_name == "Inbox":
            is_candidate = True
            reasons.append("inbox")

        if is_candidate:
            # Clone task to avoid mutating state directly, add metadata
            c = task.copy()
            c["planner_reasons"] = reasons
            candidates.append(c)

    return candidates

def compute_area_coverage(
    state: State, 
    profile: Profile, 
    candidates: List[Dict[str, Any]], 
    selected_ids: List[str]
) -> List[AreaCoverage]:
    """
    Calculates how well the user's plan covers their Life Areas (Health, Work, etc.).
    
    Why:
    - Preventing "Tunnel Vision". It's easy to just process the urgent stuff and forget "Health".
    - This function counts:
      1. What's open in that area (Active Counts)
      2. What's selected for the coming week (Selected Counts)
    """
    coverage_map = {} # area_name -> AreaCoverage
    
    # Initialize from Profile
    for area_name, min_touches in profile.weekly_touches.items():
        coverage_map[area_name] = AreaCoverage(
            area_name=area_name,
            total_tasks=0, # All open tasks in this area
            open_tasks=0,  # Same? Or active? using 'active_count' below
            overdue_tasks=0,
            active_count=0,
            candidate_count=0,
            selected_count=0,
            required_min_touches=min_touches,
            status="ok" # Default, re-evaluated below
        )

    # Helper to map project_id -> Area
    def get_area_for_project(pid: str) -> Optional[str]:
        pname = _get_project_name(pid, state.projects)
        if not pname: return None
        
        # Profile.areas is Dict[str, List[str]] (Area -> [SubProject, ...])
        for area, subprojects in profile.areas.items():
            if pname in subprojects:
                return area
            # Also check if pname starts with one of subprojects? Or exact match?
            # Assuming exact match for now based on description.
        return None

    # 1. Active Counts (Total Open Tasks in Area)
    for task in state.tasks:
        area = get_area_for_project(task.get("project_id"))
        if area and area in coverage_map:
            cov = coverage_map[area]
            cov.total_tasks += 1
            cov.active_count += 1
            # Check overdue
            if task.get("due") and task["due"].get("date"):
                 if task["due"]["date"] < datetime.now().strftime("%Y-%m-%d"):
                     cov.overdue_tasks += 1

    # 2. Candidate Counts
    for task in candidates:
        area = get_area_for_project(task.get("project_id"))
        if area and area in coverage_map:
            coverage_map[area].candidate_count += 1
            
    # 3. Selected Counts
    # We need to find the specific tasks for selected_ids.
    # We can look in candidates (mostly) or state.tasks (if user selected something else?)
    # For now assuming user selects from candidates OR search.
    # Actually, we just need to know which area the selected tasks belong to.
    
    # We'll stick to State for lookup to be safe
    for task in state.tasks:
        if task["id"] in selected_ids:
            area = get_area_for_project(task.get("project_id"))
            if area and area in coverage_map:
                coverage_map[area].selected_count += 1

    # 4. Status Evaluation
    results = []
    for area_name, cov in coverage_map.items():
        if cov.selected_count < cov.required_min_touches:
            cov.status = "missing"
        else:
            cov.status = "ok"
        results.append(cov)
        
    return results

def check_coverage_gate(coverage: List[AreaCoverage], skipped_areas: Dict[str, str]) -> List[Issue]:
    """
    Check if any 'missing' areas are not explained/skipped.
    skipped_areas: { area_name: reason }
    """
    issues = []
    for cov in coverage:
        if cov.status == "missing":
            if cov.area_name in skipped_areas:
                cov.status = "skipped"
                cov.missing_reason = skipped_areas[cov.area_name]
            else:
                # Blocking issue
                issues.append(Issue(
                    id=f"missing_coverage_{cov.area_name}",
                    title=f"Missing Coverage: {cov.area_name}",
                    description=f"You need {cov.required_min_touches} tasks, but selected {cov.selected_count}.",
                    severity="high"
                ))
    return issues

def generate_draft(
    session_data: Dict[str, Any], 
    state: State,
    candidates: List[Dict[str, Any]]
) -> WeeklyPlanDraft:
    """
    Construct the final draft object.
    session_data should contain: 
    - selected_task_ids
    - focus_areas
    - top_priorities
    - notes
    """
    selected_ids = session_data.get("selected_task_ids", [])
    
    # Hydrate selected tasks
    selected_tasks = []
    
    # Use a lookup from candidates first (has reason tags), then state
    cand_map = {c["id"]: c for c in candidates}
    
    for tid in selected_ids:
        t_data = {}
        if tid in cand_map:
            t_data = cand_map[tid]
        else:
            # Find in state
            found = next((t for t in state.tasks if t["id"] == tid), None)
            if found:
                t_data = found.copy()
            else:
                continue # Should not happen
        
        # Ensure we have planner_reasons initialized if coming from raw state
        if "planner_reasons" not in t_data:
            t_data["planner_reasons"] = []
            
        t_data["planner_reasons"].append("selected")
        selected_tasks.append(t_data)
        
    return WeeklyPlanDraft(
        focus_areas=session_data.get("focus_areas", []),
        top_priorities=session_data.get("top_priorities", []),
        notes=session_data.get("notes", ""),
        selected_tasks=selected_tasks
    )

def _get_project_name(pid: str, projects: List[Dict[str, Any]]) -> Optional[str]:
    for p in projects:
        if p["id"] == pid:
            return p["name"]
    return None

def generate_plan_application_actions(draft: WeeklyPlanDraft, options: Dict[str, Any]) -> List[Action]:
    """
    Generate actions to apply the plan to Todoist.
    options:
        - set_priorities: bool (If True, sets priority to P2 (API 3) if currently lower)
        - add_label: Optional[str] (If set, adds this label)
        - add_comment: Optional[str] (If set, adds this comment)
    """
    actions: List[Action] = []
    
    label_to_add = options.get("add_label")
    comment_to_add = options.get("add_comment")
    set_priorities = options.get("set_priorities", False)
    
    for task in draft.selected_tasks:
        tid = task.get('id')
        if not tid:
            continue
            
        # 1. Priority
        if set_priorities:
            current_prio = task.get('priority', 1)
            # API: 4=P1, 3=P2, 2=P3, 1=P4.
            # We want to ensure at least P2 (API 3).
            if current_prio < 3:
                actions.append({
                    "type": "update_task",
                    "id": tid,
                    "priority": 3 
                })
        
        # 2. Label
        if label_to_add and label_to_add.strip():
            lbl = label_to_add.strip()
            actions.append({
                "type": "add_label",
                "task_id": tid,
                "label": lbl
            })
            
        # 3. Comment
        if comment_to_add and comment_to_add.strip():
            cmt = comment_to_add.strip()
            actions.append({
                "type": "add_comment",
                "task_id": tid,
                "content": cmt
            })
            
    return actions
