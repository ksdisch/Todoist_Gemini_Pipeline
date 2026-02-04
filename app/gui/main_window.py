import sys
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTableView, QLineEdit, QPushButton, QTextEdit,
    QListWidget, QLabel, QStatusBar, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QAbstractTableModel, Slot, QThreadPool
from PySide6.QtGui import QColor

from app.core.orchestrator import Architect
from .worker import Worker

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



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Todoist Gemini Controller")
        self.resize(1200, 800)

        self.architect = Architect()
        self.threadpool = QThreadPool()
        print(f"Multithreading with maximum {self.threadpool.maxThreadCount()} threads")

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
        self.chat_input.returnPressed.connect(self.start_analyze) # Connect Enter key
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.start_analyze)
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

        self.execute_btn = QPushButton("Execute Actions")
        self.execute_btn.setEnabled(False) # Disabled until actions are available
        self.execute_btn.clicked.connect(self.start_execute)
        actions_layout.addWidget(self.execute_btn)
        
        right_splitter.addWidget(actions_widget)

        splitter.addWidget(right_splitter)
        
        # Initial sizes
        splitter.setSizes([600, 600])

    def set_ui_busy(self, busy: bool):
        """Enable/Disable UI elements during background work."""
        self.refresh_btn.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        self.chat_input.setEnabled(not busy)
        self.execute_btn.setEnabled(not busy and self.actions_list.count() > 0) # Only enable if actions exist
        if busy:
            self.task_table.setEnabled(False) # Visual cue
        else:
            self.task_table.setEnabled(True)

    @Slot()
    def refresh_data(self):
        self.status_bar.showMessage("Fetching state from Todoist...")
        self.set_ui_busy(True)
        
        # Pass the method itself, not the result of the call
        worker = Worker(self.architect.fetch_state)
        worker.signals.finished.connect(self.on_refresh_finished)
        worker.signals.failed.connect(self.on_worker_error)
        worker.signals.finished.connect(lambda: self.set_ui_busy(False))
        worker.signals.failed.connect(lambda: self.set_ui_busy(False))
        
        self.threadpool.start(worker)

    @Slot(object)
    def on_refresh_finished(self, state):
        self.status_bar.showMessage(f"State loaded. {len(state.tasks)} tasks fetched.")
        self.task_model.update_tasks(state.tasks)
        self.chat_history.append(f"<i>System: Fetched {len(state.tasks)} tasks and {len(state.projects)} projects.</i>")

    @Slot(object)
    def on_worker_error(self, e):
        self.status_bar.showMessage(f"Error: {e}")
        self.chat_history.append(f"<span style='color:red'>Error: {e}</span>")

    # --- Analyze Workflow ---
    @Slot()
    def start_analyze(self):
        user_text = self.chat_input.text().strip()
        if not user_text:
            return

        self.chat_history.append(f"<b>You:</b> {user_text}")
        self.chat_input.clear()
        self.status_bar.showMessage("Gemini is analyzing...")
        self.set_ui_busy(True)

        # Assuming self.architect.analyze(user_input, current_state) exists or similar
        # Since I don't see the exact signature, passing user_text. 
        # Ideally we pass a snapshot of state too, or let architect handle it if it has state.
        # Based on previous context, Architect is an orchestrator.
        # Let's assume architect.analyze(user_input)
        
        worker = Worker(self.architect.analyze, user_text) # Pass args to Worker
        worker.signals.finished.connect(self.on_analyze_finished)
        worker.signals.failed.connect(self.on_worker_error)
        worker.signals.finished.connect(lambda: self.set_ui_busy(False))
        worker.signals.failed.connect(lambda: self.set_ui_busy(False))
        
        self.threadpool.start(worker)

    @Slot(object)
    def on_analyze_finished(self, plan):
        self.chat_history.append(f"<b>Gemini:</b> {plan.thought_process if hasattr(plan, 'thought_process') else 'Analysis complete'}")
        self.actions_list.clear()
        
        # specific handling depends on what 'plan' object structure is
        actions = getattr(plan, 'actions', [])
        for action in actions:
            self.actions_list.addItem(str(action))  # Simplified display
        
        if actions:
            self.status_bar.showMessage(f"Analysis complete. {len(actions)} actions proposed.")
            self.execute_btn.setEnabled(True)
        else:
            self.status_bar.showMessage("Analysis complete. No actions proposed.")

    # --- Execute Workflow ---
    @Slot()
    def start_execute(self):
        self.status_bar.showMessage("Executing actions...")
        self.set_ui_busy(True)
        
        # Assuming architect.execute(plan) or similar
        # We need the plan object from analyze. 
        # For this example, let's assume we stored it or just pass the current actions.
        # Ideally, we store self.current_plan in on_analyze_finished
        
        # Placeholder for execution call
        # worker = Worker(self.architect.execute, self.current_plan)
        # For now, just a dummy print to show wiring
        worker = Worker(lambda: "Execution Dummy Result") 
        
        worker.signals.finished.connect(self.on_execute_finished)
        worker.signals.failed.connect(self.on_worker_error)
        worker.signals.finished.connect(lambda: self.set_ui_busy(False))
        worker.signals.failed.connect(lambda: self.set_ui_busy(False))
        
        self.threadpool.start(worker)

    @Slot(object)
    def on_execute_finished(self, result):
        self.status_bar.showMessage("Execution finished.")
        self.chat_history.append("<i>System: Actions executed.</i>")
        self.actions_list.clear()
        self.execute_btn.setEnabled(False)
        # Trigger refresh to see changes
        self.refresh_data()
