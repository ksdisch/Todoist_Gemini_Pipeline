from datetime import datetime
from app.core.config import CONTEXT_CONFIG

def format_task(task, projects):
    """Formats a single task for AI context."""
    project_map = {p['id']: p for p in projects} if isinstance(projects, list) else projects
    p_name = project_map.get(task.get('project_id'), {}).get('name', 'Unknown')
    return f"ID: {task['id']} | Content: {task['content']} | Priority: {task['priority']} | Due: {(task.get('due') or {}).get('string', 'None')} | Project: {p_name}"

def is_task_relevant(task, inbox_project_id):
    """Determines if a task is relevant based on context config."""
    # 1. Check Inbox
    if CONTEXT_CONFIG['always_show_inbox'] and task.get('project_id') == inbox_project_id:
        return True, "Inbox"

    # 2. Check Priority (Todoist API: 4=Urgent, 1=Low)
    if task.get('priority', 1) >= CONTEXT_CONFIG['min_priority']:
        return True, "High Priority"

    # 3. Check Due Date
    due = task.get('due')
    if due and due.get('date'):
        try:
            due_date = datetime.strptime(due['date'], "%Y-%m-%d").date()
            today = datetime.now().date()
            days_diff = (due_date - today).days

            if CONTEXT_CONFIG['include_overdue'] and days_diff < 0:
                return True, "Overdue"
            
            if 0 <= days_diff <= CONTEXT_CONFIG['due_soon_days']:
                return True, "Due Soon"
        except ValueError:
            pass # Ignore parsing errors

    return False, "Low Priority / Far Future"

def format_state_for_ai(tasks, projects):
    """Formats current state for the AI context with optimized filtering."""
    
    # Map projects for easy lookup
    project_map = {p['id']: p for p in projects}
    inbox_project = next((p for p in projects if p.get('is_inbox_project') or p.get('name') == 'Inbox'), None)
    inbox_id = inbox_project['id'] if inbox_project else "unknown"

    focus_tasks = []
    summary_data = {} # project_id -> count

    # Optimization: Skip complex filtering for small lists to maximize context
    filtering_enabled = len(tasks) > CONTEXT_CONFIG.get('skip_filter_threshold', 0)

    for t in tasks:
        # If filtering is disabled, treat everything as relevant (Focus)
        if not filtering_enabled:
            focus_tasks.append(t)
            continue

        is_relevant, reason = is_task_relevant(t, inbox_id)
        if is_relevant:
            focus_tasks.append(t)
        else:
            p_id = t.get('project_id')
            if p_id not in summary_data:
                summary_data[p_id] = 0
            summary_data[p_id] += 1

    # Format Focus Tasks
    task_lines = []
    for t in focus_tasks:
        p_name = project_map.get(t.get('project_id'), {}).get('name', 'Unknown')
        task_lines.append(f"ID: {t['id']} | Content: {t['content']} | Priority: {t['priority']} | Due: {(t.get('due') or {}).get('string', 'None')} | Project: {p_name}")

    # Format Summaries
    summary_lines = []
    for p_id, count in summary_data.items():
        p_name = project_map.get(p_id, {}).get('name', 'Unknown')
        summary_lines.append(f"{p_name}: {count} other tasks hidden (low priority/future)")

    project_lines = []
    for p in projects:
        project_lines.append(f"ID: {p['id']} | Name: {p['name']}")
        
    return f"""
Current Projects:
{chr(10).join(project_lines)}

Focus Tasks (Overdue, Due Soon, High Priority, or Inbox):
{chr(10).join(task_lines) if task_lines else "No focus tasks."}

Task Summaries (Hidden):
{chr(10).join(summary_lines) if summary_lines else "No other tasks."}
"""
