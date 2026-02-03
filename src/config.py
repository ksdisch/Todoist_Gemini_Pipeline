import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TODOIST_API_TOKEN = os.getenv("TODOIST_API_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TODOIST_API_TOKEN or not GEMINI_API_KEY:
    # We might not want to raise error immediately on import if testing, 
    # but for the app it's critical. 
    # Let's just warn or handle it in main.
    pass

# ================= CONTEXT OPTIMIZATION CONFIG =================
CONTEXT_CONFIG = {
    'min_priority': 3,       # Include tasks with priority >= 3 (3=High, 4=Urgent)
    'due_soon_days': 3,      # Include tasks due within this many days
    'always_show_inbox': True,
    'include_overdue': True,
    'skip_filter_threshold': 30 # Show all tasks if total count is <= 30
}
