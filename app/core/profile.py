import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class SectionNames:
    active: str = "Active"
    someday: str = "Someday/Maybe"
    reference: str = "Reference"

@dataclass
class Profile:
    name: str = "Default"
    section_names: SectionNames = field(default_factory=SectionNames)
    waiting_label: str = "Waiting"
    areas: Dict[str, List[str]] = field(default_factory=dict)  # AreaName -> [SubProject1, SubProject2]
    weekly_touches: Dict[str, int] = field(default_factory=dict) # AreaName -> Minimum touches
    exclusions: List[str] = field(default_factory=list) # List of project/section names to exclude

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Profile':
        section_data = data.get("section_names", {})
        return cls(
            name=data.get("name", "Default"),
            section_names=SectionNames(
                active=section_data.get("active", "Active"),
                someday=section_data.get("someday", "Someday/Maybe"),
                reference=section_data.get("reference", "Reference")
            ),
            waiting_label=data.get("waiting_label", "Waiting"),
            areas=data.get("areas", {}),
            weekly_touches=data.get("weekly_touches", {}),
            exclusions=data.get("exclusions", [])
        )

def load_profile(path: str) -> Profile:
    """
    Load a profile from a JSON file.
    If path doesn't exist or is invalid, returns a default Profile.
    """
    if not os.path.exists(path):
        return Profile()
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            return Profile.from_dict(data)
    except Exception as e:
        print(f"Error loading profile from {path}: {e}")
        return Profile()
