
import pytest
from app.core.weekly_review.models import WeeklyPlanDraft
from app.core.weekly_review.planner import generate_plan_application_actions

def test_generate_plan_actions_priority():
    draft = WeeklyPlanDraft(selected_tasks=[
        {"id": "t1", "priority": 1}, # P4 (Grey) -> Should go to 3 (Orange)
        {"id": "t2", "priority": 4}, # P1 (Red) -> Should stay
        {"id": "t3", "priority": 3}, # P2 (Orange) -> Should stay
    ])
    
    options = {"set_priorities": True}
    actions = generate_plan_application_actions(draft, options)
    
    assert len(actions) == 1
    assert actions[0]["type"] == "update_task"
    assert actions[0]["id"] == "t1"
    assert actions[0]["priority"] == 3

def test_generate_plan_actions_label():
    draft = WeeklyPlanDraft(selected_tasks=[
        {"id": "t1"},
        {"id": "t2"},
    ])
    
    options = {"add_label": "this_week"}
    actions = generate_plan_application_actions(draft, options)
    
    assert len(actions) == 2
    assert actions[0]["type"] == "add_label"
    assert actions[0]["task_id"] == "t1"
    assert actions[0]["label"] == "this_week"

def test_generate_plan_actions_comment():
    draft = WeeklyPlanDraft(selected_tasks=[
        {"id": "t1"},
    ])
    
    options = {"add_comment": "Weekly Focus"}
    actions = generate_plan_application_actions(draft, options)
    
    assert len(actions) == 1
    assert actions[0]["type"] == "add_comment"
    assert actions[0]["task_id"] == "t1"
    assert actions[0]["content"] == "Weekly Focus"

def test_generate_plan_actions_mixed():
    draft = WeeklyPlanDraft(selected_tasks=[
        {"id": "t1", "priority": 1},
    ])
    
    options = {
        "set_priorities": True,
        "add_label": "lbl",
        "add_comment": "cmt"
    }
    actions = generate_plan_application_actions(draft, options)
    
    assert len(actions) == 3
    types = {a["type"] for a in actions}
    assert types == {"update_task", "add_label", "add_comment"}

def test_generate_plan_actions_empty_options():
    draft = WeeklyPlanDraft(selected_tasks=[{"id": "t1"}])
    options = {}
    actions = generate_plan_application_actions(draft, options)
    assert len(actions) == 0
