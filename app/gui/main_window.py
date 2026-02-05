import sys
import json
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTableView, QLineEdit, QPushButton, QTextEdit,
    QListWidget, QLabel, QStatusBar, QHeaderView, QAbstractItemView,
    QMessageBox, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, QAbstractTableModel, Slot, QThreadPool
from PySide6.QtGui import QColor

# =================================================================================================
# TOUR HEADER: Main Window (GUI Root)
# =================================================================================================
#
# JOB: 
# This is the root of the Graphical User Interface. It assembles the "Lego blocks" of widgets
# into the final application.
#
# WIRING:
# The Main Window connects the GUI events (clicks) to the Core Logic (Architect).
# - "Refresh" Click -> Calls Architect.fetch_state() (via Worker)
# - "Send" Click -> Calls Architect.analyze() (via Worker)
# - "Execute" Click (in Widget) -> Main Window listens to signal -> Updates State.
#
# THREADING MODEL:
# All standard Python code runs on the Main Thread. Network calls MUST be offloaded to 
# self.threadpool using the Worker class to avoid freezing the UI.
#
# =================================================================================================

from app.core.orchestrator import Architect
from .worker import Worker
from .action_model import ActionModel
from .widgets import ActionsWidget, ResultsWidget
from .weekly_review_tab import WeeklyReviewTab

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

        self.current_state = None

        self.setup_ui()
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # Main Layout is now just vertical for the tab widget
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.main_tabs = QTabWidget()
        main_layout.addWidget(self.main_tabs)

        # === TAB 1: Dashboard (Tasks + Chat) ===
        dashboard_tab = QWidget()
        dashboard_layout = QVBoxLayout(dashboard_tab)
        
        # Splitter (Left vs Right)
        splitter = QSplitter(Qt.Horizontal)
        dashboard_layout.addWidget(splitter)

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

        # Session Info Footer
        self.session_info_label = QLabel("Session Info: Not connected")
        self.session_info_label.setStyleSheet("color: gray; font-size: 10pt;")
        left_layout.addWidget(self.session_info_label)

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

        # Actions Area (Tabs for Proposal vs Results)
        self.action_tabs = QTabWidget()
        right_splitter.addWidget(self.action_tabs)

        # --- Dashboard Actions Widget ---
        self.actions_widget = ActionsWidget(self.architect, self.threadpool)
        self.actions_widget.status_message.connect(self.update_status)
        self.actions_widget.execution_finished.connect(self.on_execution_complete)
        self.actions_widget.undo_finished.connect(self.on_undo_complete)
        self.actions_widget.busy_state_changed.connect(self.on_child_busy)
        self.actions_widget.chk_dry_run.toggled.connect(self.update_session_info)
        
        self.action_tabs.addTab(self.actions_widget, "Proposed Actions")
        
        # --- Dashboard Results Widget ---
        self.results_widget = ResultsWidget()
        self.action_tabs.addTab(self.results_widget, "Execution Results")

        splitter.addWidget(right_splitter)
        splitter.setSizes([600, 600])

        self.main_tabs.addTab(dashboard_tab, "Daily Dashboard")

        # === TAB 2: Weekly Review ===
        self.weekly_review_tab = WeeklyReviewTab(self.architect, self.threadpool)
        self.weekly_review_tab.status_message.connect(self.update_status)
        # Assuming we might want to refresh main state if Review alters things (not wired yet fully)
        
        self.main_tabs.addTab(self.weekly_review_tab, "Weekly Review")

    def set_ui_busy(self, busy: bool):
        """Enable/Disable UI elements during background work."""
        self.refresh_btn.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        self.chat_input.setEnabled(not busy)
        
        self.actions_widget.set_ui_busy(busy)
        
        if busy:
            self.task_table.setEnabled(False) 
        else:
            self.task_table.setEnabled(True)

    @Slot(str)
    def update_status(self, msg):
        self.status_bar.showMessage(msg)

    @Slot(bool)
    def on_child_busy(self, busy):
        """Called when ActionsWidget becomes busy/idle internally (execute/undo)."""
        self.set_ui_busy(busy)

    @Slot()
    def refresh_data(self):
        """
        Triggers a full state refresh from Todoist.
        
        Flow:
        1. Set UI to Busy (disable buttons).
        2. Spawn Worker thread to run architect.fetch_state().
        3. On Finish: update_tasks table, sync state to AI, re-enable UI.
        """
        self.status_bar.showMessage("Fetching state from Todoist...")
        self.set_ui_busy(True)
        
        worker = Worker(self.architect.fetch_state)
        worker.signals.finished.connect(self.on_refresh_finished)
        worker.signals.failed.connect(self.on_worker_error)
        worker.signals.finished.connect(lambda: self.set_ui_busy(False))
        worker.signals.failed.connect(lambda: self.set_ui_busy(False))
        
        self.threadpool.start(worker)

    @Slot(object)
    def on_refresh_finished(self, state):
        self.current_state = state
        self.status_bar.showMessage(f"State loaded. {len(state.tasks)} tasks fetched.")
        self.task_model.update_tasks(state.tasks)
        self.chat_history.append(f"<i>System: Fetched {len(state.tasks)} tasks and {len(state.projects)} projects.</i>")
        
        self.update_session_info()
        self.architect.sync_state(state)
        
        # Sync to Weekly Review Tab
        self.weekly_review_tab.set_current_state(state)

    def update_session_info(self):
        """Updates the session info label based on current state."""
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        
        task_count = len(self.current_state.tasks) if self.current_state else 0
        proj_count = len(self.current_state.projects) if self.current_state else 0
        
        is_dry_run = self.actions_widget.chk_dry_run.isChecked()
        mode_str = "Dry Run" if is_dry_run else "Live Mode"
        
        self.session_info_label.setText(
            f"Last Refreshed: {now} | Tasks: {task_count} | Projects: {proj_count} | Mode: {mode_str}"
        )

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

        if not self.current_state:
            self.status_bar.showMessage("⚠️ Please refresh state before sending a message.")
            self.chat_history.append("<i>System: Please click 'Refresh State' first.</i>")
            return

        self.chat_history.append(f"<b>You:</b> {user_text}")
        self.chat_input.clear()
        self.status_bar.showMessage("Gemini is analyzing...")
        self.set_ui_busy(True)

        worker = Worker(self.architect.analyze, self.current_state, user_text)
        worker.signals.finished.connect(self.on_analyze_finished)
        worker.signals.failed.connect(self.on_worker_error)
        worker.signals.finished.connect(lambda: self.set_ui_busy(False))
        worker.signals.finished.connect(lambda: self.action_tabs.setCurrentIndex(0)) # Switch to Actions tab
        worker.signals.failed.connect(lambda: self.set_ui_busy(False))
        
        self.threadpool.start(worker)

    @Slot(object)
    def on_analyze_finished(self, result):
        thought = result.get("thought", "Analysis complete.")
        actions = result.get("actions", [])
        
        self.chat_history.append(f"<b>Gemini:</b> {thought}")
        self.actions_widget.set_actions(actions)
        
        if actions:
            self.status_bar.showMessage(f"Analysis complete. {len(actions)} actions proposed.")
        else:
            self.status_bar.showMessage("Analysis complete. No actions proposed.")

    # --- Execution Callbacks ---
    @Slot(object, bool)
    def on_execution_complete(self, results, dry_run):
        self.status_bar.showMessage("Execution finished.")
        self.chat_history.append(f"<i>System: {'Simulated' if dry_run else 'Executed'} {len(results)} actions.</i>")
        
        self.results_widget.display_results(results, self.actions_widget.action_model)
        self.action_tabs.setCurrentIndex(1)
        
        if not dry_run:
            success_count = sum(1 for r in results if r.get("success"))
            if success_count > 0:
                self.refresh_data()

    @Slot(object)
    def on_undo_complete(self, results):
        self.status_bar.showMessage("Undo complete.")
        self.chat_history.append(f"<i>System: Undid {len(results)} actions.</i>")
        
        self.results_widget.display_results(results, self.actions_widget.action_model)
        self.action_tabs.setCurrentIndex(1)
        self.refresh_data()
