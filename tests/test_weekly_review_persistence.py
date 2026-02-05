import sys
import os
from datetime import datetime
import shutil

# Set env var BEFORE importing app modules
os.environ["WEEKLY_REVIEW_STORAGE_DIR"] = os.path.join(os.getcwd(), "temp_reviews")

# Adjust path to include app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.weekly_review import engine, persistence, models

def test_persistence():
    print(f"Testing Persistence in {os.environ['WEEKLY_REVIEW_STORAGE_DIR']}...")
    
    # 1. Create dummy session
    session = models.ReviewSession(
        id="test_session_" + datetime.now().strftime("%Y%m%d%H%M%S"),
        start_time=datetime.now()
    )
    
    # 2. Add some data
    session.scores["step_1"] = 2
    session.outcomes = ["Win 1", "Win 2", "Win 3"]
    session.status = "completed"
    session.completed_at = datetime.now()
    
    # 3. Save
    path = persistence.save_session(session)
    print(f"Saved to {path}")
    
    # 4. Load
    loaded = persistence.load_session(session.id)
    assert loaded.id == session.id
    assert loaded.scores["step_1"] == 2
    assert len(loaded.outcomes) == 3
    print("Loaded verification success.")
    
    # 5. List metadata
    meta = persistence.list_sessions_metadata()
    found = False
    for m in meta:
        if m["id"] == session.id:
            found = True
            print(f"Found metadata: {m}")
            assert m["total_score"] == 2
            break
            
    assert found
    print("Metadata listing success.")

if __name__ == "__main__":
    test_persistence()
