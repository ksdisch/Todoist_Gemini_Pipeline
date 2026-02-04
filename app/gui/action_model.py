
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

DESTRUCTIVE_TYPES = {"close_task", "delete_task", "delete_project", "remove_label"}

class ActionModel(QAbstractTableModel):
    """Model for displaying proposed AI actions with checkboxes."""
    def __init__(self, actions=None):
        super().__init__()
        self._actions = actions or []
        # State: list of booleans matching _actions
        self._checked = [True] * len(self._actions)
        self._headers = ["", "Type", "Summary"]

    def set_actions(self, actions):
        self.beginResetModel()
        self._actions = actions
        self._checked = [True] * len(actions)
        # Calculate validity for each action
        self._validity = [self._validate_action(a) for a in actions]
        
        # Uncheck invalid actions by default
        for i, (is_valid, _) in enumerate(self._validity):
            if not is_valid:
                self._checked[i] = False
                
        self.endResetModel()

    def _validate_action(self, action):
        """
        Validates an action.
        Returns: (is_valid: bool, error_message: str)
        """
        act_type = action.get("type")
        if not act_type:
            return False, "Missing action type"
            
        required_fields = {
            "create_task": ["content"],
            "update_task": ["id"], # strict: need ID. content/priority optional (updates)
            "close_task": ["id"],
            "reopen_task": ["id"],
            "delete_task": ["id"],
            "move_task": ["id", "project_id"], # section_id strictly optional, but project_id often needed? 
                                               # actually move_task might only need ID if movement is implied? 
                                               # Todoist API usually needs project_id OR section_id. 
                                               # Let's keep it simple: need ID.
            "create_project": ["name"],
            "delete_project": ["id"],
            "create_section": ["name", "project_id"],
            "create_label": ["name"],
            "add_label": ["task_id", "label"],
            "remove_label": ["task_id", "label"],
            "add_comment": ["task_id", "content"],
            "delete_comment": ["id"],
        }
        
        # For move_task, let's refine: usually needs id. Target is optional if we assume something defaults?
        # But logically you move TO something.
        if act_type == "move_task":
            if not action.get("id"):
                return False, "Missing task ID"
            if not action.get("project_id") and not action.get("section_id"):
                 return False, "Must specify target project or section"
            return True, ""

        reqs = required_fields.get(act_type, [])
        for field in reqs:
            if not action.get(field):
                return False, f"Missing required field: {field}"
                
        return True, ""

    def get_checked_actions(self):
        return [
            action for action, checked, (valid, _) in zip(self._actions, self._checked, self._validity)
            if checked and valid
        ]

    def select_all(self, select=True):
        if not self._actions:
            return
            
        # Only select valid items
        for i in range(len(self._actions)):
            is_valid, _ = self._validity[i]
            if is_valid:
                self._checked[i] = select
            else:
                self._checked[i] = False # Always uncheck invalid
                
        start = self.index(0, 0)
        end = self.index(len(self._actions) - 1, 0)
        self.dataChanged.emit(start, end, [Qt.CheckStateRole])

    def has_destructive_selected(self):
        selected = self.get_checked_actions()
        return any(act.get("type") in DESTRUCTIVE_TYPES for act in selected)

    def rowCount(self, parent=QModelIndex()):
        return len(self._actions)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._actions)):
            return None

        row = index.row()
        col = index.column()
        action = self._actions[row]
        is_valid, error_msg = self._validity[row]

        if role == Qt.DisplayRole:
            if col == 1: # Type
                return action.get("type", "unknown")
            elif col == 2: # Summary
                summary = self._get_summary(action)
                if not is_valid:
                    return f"[INVALID] {summary}"
                return summary
        
        elif role == Qt.ToolTipRole:
            details = self._get_details(action)
            if not is_valid:
                return f"ERROR: {error_msg}\n\n{details}"
            return details

        elif role == Qt.CheckStateRole:
            if col == 0:
                if not is_valid:
                    return None # No checkbox for invalid items (or could be disabled uncheck)
                return Qt.Checked if self._checked[row] else Qt.Unchecked
            
        elif role == Qt.ForegroundRole:
            if col == 1 and action.get("type") in DESTRUCTIVE_TYPES:
                return Qt.red 
            if not is_valid:
                return Qt.darkGray
            
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid() and role == Qt.CheckStateRole and index.column() == 0:
            # Prevent checking invalid items
            is_valid, _ = self._validity[index.row()]
            if not is_valid:
                return False
                
            self._checked[index.row()] = (value == Qt.Checked)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def flags(self, index):
        default_flags = super().flags(index)
        if index.column() == 0:
            is_valid, _ = self._validity[index.row()]
            if not is_valid:
                return default_flags & ~Qt.ItemIsUserCheckable & ~Qt.ItemIsEnabled
            return default_flags | Qt.ItemIsUserCheckable | Qt.ItemIsEditable
        return default_flags

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def _get_summary(self, action):
        """Generates a human-readable summary."""
        act_type = action.get("type")
        if act_type == "create_task":
            return f"Create: {action.get('content')}"
        elif act_type == "update_task":
            changes = []
            if action.get("content"): changes.append(f"name='{action.get('content')}'")
            if action.get("priority"): changes.append(f"prio={action.get('priority')}")
            return f"Update {action.get('id')}: {', '.join(changes)}"
        elif act_type == "close_task":
            return f"Close task {action.get('id')}"
        elif act_type == "move_task":
            p = action.get('project_id', 'same')
            s = action.get('section_id', 'same')
            return f"Move {action.get('id')} to p={p} s={s}"
        elif act_type == "delete_task":
            return f"Delete task {action.get('id')}"
        elif act_type == "delete_project":
            return f"Delete project {action.get('id')}"
        elif act_type == "reopen_task":
            return f"Reopen task {action.get('id')}"
        elif act_type == "delete_comment":
             return f"Delete comment {action.get('id')}"
        elif act_type == "remove_label":
             return f"Remove label '{action.get('label')}' from {action.get('task_id')}"
        elif act_type == "add_label":
             return f"Add label '{action.get('label')}' from {action.get('task_id')}"
        # Fallback
        return str(action)

    def _get_details(self, action):
        """Generates detailed tooltip."""
        lines = [f"{k}: {v}" for k, v in action.items()]
        return "\n".join(lines)
