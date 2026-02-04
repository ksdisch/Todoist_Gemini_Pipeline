import sys
import json
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTableView, QLineEdit, QPushButton, QTextEdit,
    QListWidget, QLabel, QStatusBar, QHeaderView, QAbstractItemView,
    QMessageBox, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt, QAbstractTableModel, Slot, QThreadPool
from PySide6.QtGui import QColor

from app.core.orchestrator import Architect
from .worker import Worker
from .action_model import ActionModel

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
        # self.proposed_actions is now managed by self.action_model mostly, 
        # but we can keep a reference if needed.

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

        # Actions Area (Tabs for Proposal vs Results)
        self.tabs = QTabWidget()
        right_splitter.addWidget(self.tabs)

        # --- Tab 1: Proposed Actions ---
        actions_widget = QWidget()
        actions_layout = QVBoxLayout(actions_widget)
        
        # Action Toolbar (Select All/None + Dry Run)
        action_toolbar = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_none = QPushButton("Select None")
        self.btn_select_all.clicked.connect(lambda: self.action_model.select_all(True))
        self.btn_select_none.clicked.connect(lambda: self.action_model.select_all(False))
        
        action_toolbar.addWidget(self.btn_select_all)
        action_toolbar.addWidget(self.btn_select_none)
        action_toolbar.addStretch()
        
        # Dry Run Checkbox
        self.chk_dry_run = QCheckBox("Dry Run (simulate only)")
        self.chk_dry_run.setChecked(True) # Safer default? Or false? User said "optionally". Let's default unchecked for "Do it", or checked for safety. Let's default Unchecked to be "Execute". But maybe Checked is safer. I'll default Unchecked as standard tools usually require opt-in for dry-run.
        self.chk_dry_run.setChecked(False)
        action_toolbar.addWidget(self.chk_dry_run)
        
        actions_layout.addLayout(action_toolbar)

        # Action Table
        self.action_model = ActionModel()
        self.actions_view = QTableView()
        self.actions_view.setModel(self.action_model)
        self.actions_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Resize columns: Checkbox narrow, Type medium, Summary stretch
        header = self.actions_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        
        actions_layout.addWidget(self.actions_view)

        # Buttons
        btn_layout = QHBoxLayout()
        self.execute_btn = QPushButton("Execute Selected Actions")
        self.execute_btn.setEnabled(False) 
        self.execute_btn.clicked.connect(self.start_execute)
        
        self.copy_btn = QPushButton("Copy JSON")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self.copy_actions_to_clipboard)
        
        btn_layout.addWidget(self.execute_btn)
        btn_layout.addWidget(self.copy_btn)
        actions_layout.addLayout(btn_layout)
        
        self.tabs.addTab(actions_widget, "Proposed Actions")
        
        # --- Tab 2: Execution Results ---
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Status", "Action", "Message"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tabs.addTab(self.results_table, "Execution Results")

        splitter.addWidget(right_splitter)
        
        # Initial sizes
        splitter.setSizes([600, 600])

    def set_ui_busy(self, busy: bool):
        """Enable/Disable UI elements during background work."""
        self.refresh_btn.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        self.chat_input.setEnabled(not busy)
        
        has_actions = self.action_model.rowCount() > 0
        self.execute_btn.setEnabled(not busy and has_actions)
        self.copy_btn.setEnabled(has_actions) # Can copy even if busy
        self.btn_select_all.setEnabled(has_actions)
        self.btn_select_none.setEnabled(has_actions)
        
        if busy:
            self.task_table.setEnabled(False) # Visual cue
            self.actions_view.setEnabled(False)
        else:
            self.task_table.setEnabled(True)
            self.actions_view.setEnabled(True)

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
        self.current_state = state
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
        worker.signals.finished.connect(lambda: self.tabs.setCurrentIndex(0)) # Switch to Actions tab
        worker.signals.failed.connect(lambda: self.set_ui_busy(False))
        
        self.threadpool.start(worker)

    @Slot(object)
    def on_analyze_finished(self, result):
        thought = result.get("thought", "Analysis complete.")
        actions = result.get("actions", [])
        
        self.chat_history.append(f"<b>Gemini:</b> {thought}")
        
        # Update Action Model
        self.action_model.set_actions(actions)
        
        if actions:
            self.status_bar.showMessage(f"Analysis complete. {len(actions)} actions proposed.")
            self.execute_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)
            self.btn_select_all.setEnabled(True)
            self.btn_select_none.setEnabled(True)
        else:
            self.status_bar.showMessage("Analysis complete. No actions proposed.")
            self.execute_btn.setEnabled(False)
            self.copy_btn.setEnabled(False)
            self.btn_select_all.setEnabled(False)
            self.btn_select_none.setEnabled(False)

    # --- Execute Workflow ---
    @Slot()
    def start_execute(self):
        # 1. Get selected actions
        actions_to_run = self.action_model.get_checked_actions()
        
        if not actions_to_run:
            self.status_bar.showMessage("No actions selected.")
            return

        # 2. Check for destructive actions
        if self.action_model.has_destructive_selected():
            # Count them
            destructive_count = sum(1 for a in actions_to_run if a.get("type") in ["close_task", "delete_task", "remove_label", "delete_project"])
            
            reply = QMessageBox.question(
                self, 
                "Confirm Destructive Actions", 
                f"You are about to run {destructive_count} destructive action(s) (e.g., closing tasks, deleting items).\n\nAre you sure you want to continue?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                self.status_bar.showMessage("Execution cancelled.")
                return


        
        # 3. Execute logic (using Worker)
        is_dry_run = self.chk_dry_run.isChecked()
        
        self.status_bar.showMessage(f"{'Simulating' if is_dry_run else 'Executing'} {len(actions_to_run)} actions...")
        self.set_ui_busy(True)
        
        worker = Worker(self.architect.execute, actions_to_run, dry_run=is_dry_run) 
        
        worker.signals.finished.connect(lambda r: self.on_execute_finished(r, is_dry_run))
        worker.signals.failed.connect(self.on_worker_error)
        worker.signals.finished.connect(lambda: self.set_ui_busy(False))
        worker.signals.failed.connect(lambda: self.set_ui_busy(False))
        
        self.threadpool.start(worker)

    @Slot(object, bool)
    def on_execute_finished(self, results, dry_run):
        self.status_bar.showMessage("Execution finished.")
        success_count = sum(1 for r in results if r.get("success"))
        
        # Log to chat
        mode_str = "Simulated" if dry_run else "Executed"
        self.chat_history.append(f"<i>System: {mode_str} {len(results)} actions.</i>")
        
        # --- Populate Results Table ---
        self.results_table.setRowCount(0) # Clear
        self.results_table.setRowCount(len(results))
        
        for i, res in enumerate(results):
            # Status
            status_item = QTableWidgetItem(res.get("status", "unknown"))
            if res.get("success"):
                status_item.setForeground(QColor("green"))
            else:
                status_item.setForeground(QColor("red"))
            self.results_table.setItem(i, 0, status_item)
            
            # Action (Need summary)
            # We can use the helper from ActionModel if we made it static or accessible, 
            # OR just duplicate simple logic here or use str(),
            # OR access self.action_model._get_summary if valid.
            # Let's simple format.
            action = res.get("action", {})
            act_type = action.get("type", "unknown")
            # Quick summary
            summary = self.action_model._get_summary(action) # Reusing helper
            self.results_table.setItem(i, 1, QTableWidgetItem(summary))
            
            # Message
            msg = res.get("message", "")
            self.results_table.setItem(i, 2, QTableWidgetItem(str(msg)))

        # Switch to Results Tab
        self.tabs.setCurrentIndex(1)

        # Logic: If Dry Run, we keep actions in the Actions list so user can run real next.
        # If Real Run, we clear actions and Refresh.
        
        if not dry_run:
            if len(results) == self.action_model.rowCount() or success_count > 0:
                 # Clear actions if we actually did something
                 self.action_model.set_actions([])
                 self.execute_btn.setEnabled(False)
                 self.copy_btn.setEnabled(False)
            
            # Trigger refresh to see changes
            self.refresh_data()
        
        # If dry run, we leave actions alone.
        pass

    @Slot()
    def copy_actions_to_clipboard(self):
        actions = self.action_model.get_checked_actions()
        if not actions:
            # Maybe they want to copy all? Let's copy all visible
            actions = self.action_model._actions
            
        if not actions:
            return
        
        try:
            json_str = json.dumps(actions, indent=2)
            QApplication.clipboard().setText(json_str)
            self.status_bar.showMessage("Actions copied to clipboard!")
        except Exception as e:
            self.status_bar.showMessage(f"Failed to copy: {e}")
