import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from .models import ReviewSession, StepResult, WeeklyPlanDraft, Issue

# Define storage directory
STORAGE_DIR = Path.home() / ".todoist_gemini" / "weekly_review_sessions"

def _ensure_storage():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

def _decode_hook(dct):
    # Simple heuristic to decode datetimes
    for k, v in dct.items():
        if isinstance(v, str) and "T" in v:
            try:
                # Try parsing as datetime
                dct[k] = datetime.fromisoformat(v)
            except ValueError:
                pass
    return dct

def save_session(session: ReviewSession) -> str:
    _ensure_storage()
    filename = f"{session.id}.json"
    filepath = STORAGE_DIR / filename
    
    # manual dict conversion since dataclasses.asdict might be too recursive/strict with custom types if not careful,
    # but `dataclasses.asdict` is usually fine if everything is a dataclass.
    # Let's use `dataclasses.asdict`.
    from dataclasses import asdict
    
    data = asdict(session)
    
    with open(filepath, 'w') as f:
        json.dump(data, f, cls=DateTimeEncoder, indent=2)
        
    return str(filepath)

def load_session(session_id: str) -> Optional[ReviewSession]:
    filepath = STORAGE_DIR / f"{session_id}.json"
    if not filepath.exists():
        return None
        
    with open(filepath, 'r') as f:
        data = json.load(f, object_hook=_decode_hook)
        
    # Reconstruct objects
    # This is a bit manual because nested dataclasses don't auto-hydrate from dicts easily without a library like dacite/pydantic.
    # We'll do a basic reconstruction.
    
    completed_steps = [StepResult(**s) for s in data.get("completed_steps", [])]
    plan_draft_data = data.get("plan_draft", {})
    plan_draft = WeeklyPlanDraft(**plan_draft_data)
    
    session = ReviewSession(
        id=data["id"],
        start_time=data["start_time"],
        status=data.get("status", "in_progress"),
        current_step_id=data.get("current_step_id"),
        completed_steps=completed_steps,
        plan_draft=plan_draft
    )
    
    return session

def list_sessions() -> List[str]:
    _ensure_storage()
    return [f.stem for f in STORAGE_DIR.glob("*.json")]
