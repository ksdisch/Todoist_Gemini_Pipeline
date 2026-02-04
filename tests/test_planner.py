import pytest
from datetime import datetime, timedelta
from app.core.schemas import State
from app.core.profile import Profile
from app.core.weekly_review import planner
from app.core.weekly_review.models import AreaCoverage, Issue

# --- Fixtures ---

@pytest.fixture
def mock_profile():
    return Profile(
        name="Test Profile",
        areas={
            "Work": ["Work Project", "Deep Work"],
            "Personal": ["Personal", "Home"]
        },
        weekly_touches={
            "Work": 2,
            "Personal": 1
        }
    )

@pytest.fixture
def mock_state():
    today = datetime.now().date()
    yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    future_str = (today + timedelta(days=10)).strftime("%Y-%m-%d")
    
    tasks = [
        # Candidate: Overdue
        {"id": "t1", "content": "Overdue Task", "project_id": "p1", "due": {"date": yesterday_str}, "priority": 1},
        # Candidate: Due Soon
        {"id": "t2", "content": "Due Soon Task", "project_id": "p2", "due": {"date": tomorrow_str}, "priority": 1},
        # Candidate: High Priority (p4 = 4 in API)
        {"id": "t3", "content": "Important Task", "project_id": "p1", "due": None, "priority": 4},
        # Candidate: Inbox
        {"id": "t4", "content": "Inbox Task", "project_id": "inbox_id", "due": None, "priority": 1},
        # Not Candidate: Far future, low prio
        {"id": "t5", "content": "Future Task", "project_id": "p2", "due": {"date": future_str}, "priority": 1},
    ]
    
    projects = [
        {"id": "p1", "name": "Work Project"},
        {"id": "p2", "name": "Personal"},
        {"id": "inbox_id", "name": "Inbox"}
    ]
    
    return State(tasks=tasks, projects=projects, sections=[], formatted_context="")

# --- Tests ---

def test_build_candidates(mock_state, mock_profile):
    candidates = planner.build_candidates(mock_state, mock_profile)
    
    ids = [c["id"] for c in candidates]
    assert "t1" in ids # Overdue
    assert "t2" in ids # Due Soon
    assert "t3" in ids # High Priority
    assert "t4" in ids # Inbox
    assert "t5" not in ids # Not candidate
    
    # Check reasons
    t1 = next(c for c in candidates if c["id"] == "t1")
    assert "overdue" in t1["planner_reasons"]
    
    t3 = next(c for c in candidates if c["id"] == "t3")
    assert "high_priority" in t3["planner_reasons"]

def test_compute_area_coverage(mock_state, mock_profile):
    # Setup candidates (just t1, t2 from above for simplicity logic check)
    candidates = [
        {"id": "t1", "project_id": "p1"}, # Work Project -> Work
        {"id": "t2", "project_id": "p2"}, # Personal -> Personal
    ]
    
    # Selected: t1 and t3 (t3 is Work Project too, from State)
    # t3 is in State, so if we select it by ID, it counts.
    selected_ids = ["t1", "t3"] 
    
    coverage = planner.compute_area_coverage(mock_state, mock_profile, candidates, selected_ids)
    
    # Verify Work Area (t1, t3 selected -> 2 selected)
    work_cov = next(c for c in coverage if c.area_name == "Work")
    assert work_cov.selected_count == 2
    assert work_cov.required_min_touches == 2
    assert work_cov.status == "ok"
    
    # Verify Personal Area (0 selected)
    personal_cov = next(c for c in coverage if c.area_name == "Personal")
    assert personal_cov.selected_count == 0
    assert personal_cov.required_min_touches == 1
    assert personal_cov.status == "missing"

def test_check_coverage_gate(mock_profile):
    # coverage list with one missing
    coverage = [
        AreaCoverage("Work", 10, 5, 0, 0, 0, 2, 2, "ok"),
        AreaCoverage("Personal", 5, 2, 0, 0, 0, 0, 1, "missing")
    ]
    
    # 1. Without skip
    issues = planner.check_coverage_gate(coverage, {})
    assert len(issues) == 1
    assert issues[0].id == "missing_coverage_Personal"
    
    # 2. With skip
    skipped = {"Personal": "Busy week"}
    issues_skipped = planner.check_coverage_gate(coverage, skipped)
    assert len(issues_skipped) == 0
    # Check modification
    assert coverage[1].status == "skipped"
    assert coverage[1].missing_reason == "Busy week"

def test_generate_draft(mock_state):
    session_data = {
        "focus_areas": ["Coding"],
        "top_priorities": ["Ship It"],
        "notes": "Let's go",
        "selected_task_ids": ["t1", "t3"]
    }
    
    # Only t1 is in candidates list passed to generate_draft usually, but let's pass partial
    candidates = [{"id": "t1", "content": "Overdue", "planner_reasons": ["overdue"]}]
    
    draft = planner.generate_draft(session_data, mock_state, candidates)
    
    assert draft.focus_areas == ["Coding"]
    assert draft.notes == "Let's go"
    assert len(draft.selected_tasks) == 2
    
    # t1 should keep reasons
    t1 = next(t for t in draft.selected_tasks if t["id"] == "t1")
    assert "overdue" in t1["planner_reasons"]
    assert "selected" in t1["planner_reasons"]
    
    # t3 came from state, reasons initialized
    t3 = next(t for t in draft.selected_tasks if t["id"] == "t3")
    assert t3["planner_reasons"] == ["selected"]
