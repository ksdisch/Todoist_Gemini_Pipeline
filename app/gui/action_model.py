
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
        self.endResetModel()

    def get_checked_actions(self):
        return [
            action for action, checked in zip(self._actions, self._checked)
            if checked
        ]

    def select_all(self, select=True):
        if not self._actions:
            return
        self._checked = [select] * len(self._actions)
        # Notify that data changed for column 0 (checkboxes)
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

        if role == Qt.DisplayRole:
            if col == 1: # Type
                return action.get("type", "unknown")
            elif col == 2: # Summary
                return self._get_summary(action)
        
        elif role == Qt.ToolTipRole:
            return self._get_details(action)

        elif role == Qt.CheckStateRole:
            if col == 0:
                return Qt.Checked if self._checked[row] else Qt.Unchecked
            
        elif role == Qt.ForegroundRole:
            if col == 1 and action.get("type") in DESTRUCTIVE_TYPES:
                return Qt.red # Mark destructive actions in red
            
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid() and role == Qt.CheckStateRole and index.column() == 0:
            self._checked[index.row()] = (value == Qt.Checked)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def flags(self, index):
        default_flags = super().flags(index)
        if index.column() == 0:
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
            return f"Move {action.get('id')} to p={action.get('project_id')} s={action.get('section_id')}"
        # Fallback
        return str(action)

    def _get_details(self, action):
        """Generates detailed tooltip."""
        lines = [f"{k}: {v}" for k, v in action.items()]
        return "\n".join(lines)
