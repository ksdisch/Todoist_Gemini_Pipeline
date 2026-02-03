import requests
from src.config import TODOIST_API_TOKEN
from src.logger import setup_logger

logger = setup_logger(__name__)

def get_tasks():
    """Fetches active tasks from Todoist."""
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {"Authorization": f"Bearer {TODOIST_API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return []

def get_projects():
    """Fetches projects from Todoist."""
    url = "https://api.todoist.com/rest/v2/projects"
    headers = {"Authorization": f"Bearer {TODOIST_API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        return []
