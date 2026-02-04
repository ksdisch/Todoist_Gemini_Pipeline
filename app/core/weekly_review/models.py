from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

@dataclass
class Issue:
    id: str
    title: str
    description: str
    related_task_id: Optional[str] = None
    severity: str = "medium"  # low, medium, high

@dataclass
class AreaCoverage:
    area_name: str
    total_tasks: int
    open_tasks: int
    overdue_tasks: int
    # Can extend with specific project IDs or other metrics

@dataclass
class WeeklyPlanDraft:
    focus_areas: List[str] = field(default_factory=list)
    top_priorities: List[str] = field(default_factory=list)
    notes: str = ""

@dataclass
class StepResult:
    step_id: str
    completed_at: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    issues_resolved: List[str] = field(default_factory=list)

@dataclass
class ReviewStep:
    id: str
    title: str
    description: str
    order: int
    
    # These are conceptual; the engine will likely hold the logic mapping
    # to avoid circular imports or complex serialization of functions

@dataclass
class ReviewSession:
    id: str
    start_time: datetime
    status: str = "in_progress"  # in_progress, completed, abandoned
    current_step_id: Optional[str] = None
    completed_steps: List[StepResult] = field(default_factory=list)
    plan_draft: WeeklyPlanDraft = field(default_factory=WeeklyPlanDraft)
    
    # Transient state for the UI/Engine to track during session
    # e.g. "issues found in current step" could be stored here or calculated dynamically
    
    def get_step_result(self, step_id: str) -> Optional[StepResult]:
        for res in self.completed_steps:
            if res.step_id == step_id:
                return res
        return None
