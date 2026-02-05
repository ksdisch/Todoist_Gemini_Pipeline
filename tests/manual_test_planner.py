
import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.getcwd())

try:
    from app.core.weekly_review.models import WeeklyPlanDraft
    from app.core.weekly_review.planner import generate_plan_application_actions
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test_priority():
    print("Testing Priority...")
    draft = WeeklyPlanDraft(selected_tasks=[
        {"id": "t1", "priority": 1},
        {"id": "t2", "priority": 4},
    ])
    options = {"set_priorities": True}
    actions = generate_plan_application_actions(draft, options)
    assert len(actions) == 1
    assert actions[0]["id"] == "t1"
    assert actions[0]["priority"] == 3
    print("PASS")

def test_label():
    print("Testing Label...")
    draft = WeeklyPlanDraft(selected_tasks=[{"id": "t1"}])
    options = {"add_label": "this_week"}
    actions = generate_plan_application_actions(draft, options)
    assert len(actions) == 1
    assert actions[0]["type"] == "add_label"
    assert actions[0]["label"] == "this_week"
    print("PASS")

def test_comment():
    print("Testing Comment...")
    draft = WeeklyPlanDraft(selected_tasks=[{"id": "t1"}])
    options = {"add_comment": "Focus"}
    actions = generate_plan_application_actions(draft, options)
    assert len(actions) == 1
    assert actions[0]["type"] == "add_comment"
    assert actions[0]["content"] == "Focus"
    print("PASS")

if __name__ == "__main__":
    try:
        test_priority()
        test_label()
        test_comment()
        print("ALL TESTS PASSED")
    except AssertionError as e:
        print(f"TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
