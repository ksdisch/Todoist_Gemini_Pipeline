import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from .models import ReviewSession, StepResult, WeeklyPlanDraft, Issue

# Define storage directory
env_path = os.environ.get("WEEKLY_REVIEW_STORAGE_DIR")
if env_path:
    STORAGE_DIR = Path(env_path)
else:
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
    if plan_draft_data:
        plan_draft = WeeklyPlanDraft(**plan_draft_data)
    else:
        plan_draft = WeeklyPlanDraft()
    
    session = ReviewSession(
        id=data["id"],
        start_time=data["start_time"],
        completed_at=data.get("completed_at"),
        status=data.get("status", "in_progress"),
        current_step_id=data.get("current_step_id"),
        completed_steps=completed_steps,
        plan_draft=plan_draft,
        scores=data.get("scores", {}),
        outcomes=data.get("outcomes", [])
    )
    
    return session

def list_sessions_metadata() -> List[Dict[str, Any]]:
    """Return lightweight summary of all sessions for history list."""
    _ensure_storage()
    metadata_list = []
    
    # helper
    def get_score_total(scores):
        if not scores: return 0
        return sum(scores.values())

    files = sorted(STORAGE_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
    
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                # We can do a partial read or full read. Full read is fine for now.
                data = json.load(f, object_hook=_decode_hook)
                
            scores = data.get("scores", {})
            metadata_list.append({
                "id": data["id"],
                "start_time": data["start_time"],
                "completed_at": data.get("completed_at"),
                "status": data.get("status"),
                "total_score": get_score_total(scores),
                "outcomes_count": len(data.get("outcomes", [])),
                "outcomes": data.get("outcomes", [])
            })
        except Exception as e:
            # skip bad files
            print(f"Error reading session {filepath}: {e}")
            continue
            
    return metadata_list

def list_sessions() -> List[str]:
    _ensure_storage()
    return [f.stem for f in STORAGE_DIR.glob("*.json")]
