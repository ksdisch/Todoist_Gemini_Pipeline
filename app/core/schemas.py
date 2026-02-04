from typing import List, Optional, Any, Dict, TypedDict
from dataclasses import dataclass

class Action(TypedDict, total=False):
    type: str
    id: Optional[str]
    content: Optional[str] 
    name: Optional[str]
    priority: Optional[int]
    project_id: Optional[str]
    section_id: Optional[str]
    labels: Optional[List[str]]
    label: Optional[str]
    due_string: Optional[str]
    task_id: Optional[str] # For comments/labels
    # Add other fields as necessary
    
class ActionResult(TypedDict):
    action: Action
    status: str
    message: str
    api_call: str
    success: bool
    undo_action: Optional[Action]

class AnalysisResult(TypedDict):
    thought: str
    actions: List[Action]

@dataclass
class State:
    tasks: List[Dict[str, Any]]
    projects: List[Dict[str, Any]]
    sections: List[Dict[str, Any]]
    formatted_context: str
