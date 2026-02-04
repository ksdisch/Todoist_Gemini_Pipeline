import sys
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTableView, QLineEdit, QPushButton, QTextEdit,
    QListWidget, QLabel, QStatusBar, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QAbstractTableModel, Slot, QThread, Signal
from PySide6.QtGui import QColor

from app.core.orchestrator import Architect

class TaskModel(QAbstractTableModel):
    """Model for displaying Todoist tasks."""
    def __init__(self, tasks: List[Dict[str, Any]] = None):
        super().__init__()
        self._tasks = tasks or []
        self._headers = ["Content", "Project", "Priority", "Due"]

    def rowCount(self, parent=None):
        return len(self._tasks)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._tasks)):
            return None

        task = self._tasks[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return task.get("content", "")
            elif col == 1:
                return task.get("project_id", "")  # In a real app we'd map ID to name
            elif col == 2:
                return str(task.get("priority", ""))
            elif col == 3:
                due = task.get("due")
                return due.get("string") if due else ""
        
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def update_tasks(self, tasks: List[Dict[str, Any]]):
        self.beginResetModel()
        self._tasks = tasks
        self.endResetModel()

class Worker(QThread):
    """Worker thread for fetching state to avoid blocking UI."""
    finished = Signal(object) # Emits the State object
    error = Signal(str)

    def __init__(self, architect):
        super().__init__()
        self.architect = architect

    def run(self):
        try:
            state = self.architect.fetch_state()
            self.finished.emit(state)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Todoist Gemini Controller")
        self.resize(1200, 800)

        self.architect = Architect()
        self.worker = None

        self.setup_ui()
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Main Splitter (Left vs Right)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- Left Pane: Tasks ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Search & Refresh
        top_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search tasks...")
        self.refresh_btn = QPushButton("Refresh State")
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        top_bar.addWidget(self.search_input)
        top_bar.addWidget(self.refresh_btn)
        left_layout.addLayout(top_bar)

        # Table
        self.task_model = TaskModel()
        self.task_table = QTableView()
        self.task_table.setModel(self.task_model)
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        left_layout.addWidget(self.task_table)

        splitter.addWidget(left_widget)

        # --- Right Pane: Chat & Actions ---
        right_splitter = QSplitter(Qt.Vertical)
        
        # Chat Pane
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.addWidget(QLabel("<b>Gemini Chat</b>"))
        
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        chat_layout.addWidget(self.chat_history)
        
        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ask Gemini to organize your tasks...")
        self.send_btn = QPushButton("Send")
        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(self.send_btn)
        chat_layout.addLayout(input_layout)
        
        right_splitter.addWidget(chat_widget)

        # Actions Pane
        actions_widget = QWidget()
        actions_layout = QVBoxLayout(actions_widget)
        actions_layout.addWidget(QLabel("<b>Proposed Actions</b>"))
        
        self.actions_list = QListWidget() # Simple list for now
        actions_layout.addWidget(self.actions_list)
        
        right_splitter.addWidget(actions_widget)

        splitter.addWidget(right_splitter)
        
        # Initial sizes
        splitter.setSizes([600, 600])

    @Slot()
    def refresh_data(self):
        self.status_bar.showMessage("Fetching state from Todoist...")
        self.refresh_btn.setEnabled(False)
        
        self.worker = Worker(self.architect)
        self.worker.finished.connect(self.on_refresh_finished)
        self.worker.error.connect(self.on_refresh_error)
        self.worker.start()

    @Slot(object)
    def on_refresh_finished(self, state):
        self.status_bar.showMessage(f"State loaded. {len(state.tasks)} tasks fetched.")
        self.refresh_btn.setEnabled(True)
        self.task_model.update_tasks(state.tasks)

        # Log to chat for visibility
        self.chat_history.append(f"<i>System: Fetched {len(state.tasks)} tasks and {len(state.projects)} projects.</i>")

    @Slot(str)
    def on_refresh_error(self, error_msg):
        self.status_bar.showMessage(f"Error: {error_msg}")
        self.refresh_btn.setEnabled(True)
        self.chat_history.append(f"<span style='color:red'>Error fetching state: {error_msg}</span>")
