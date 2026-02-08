import json
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, 
    QTableView, QHeaderView, QAbstractItemView, QMessageBox, 
    QTableWidget, QTableWidgetItem, QDialog, QDialogButtonBox, 
    QLabel, QListWidget, QApplication, QTextEdit, QFrame
)
from PySide6.QtCore import Qt, Slot, Signal, QThreadPool
from PySide6.QtGui import QColor

from .action_model import ActionModel
from .worker import Worker
from app.ui.theme.tokens import Spacing, BorderRadius, FontSize

class UndoDialog(QDialog):
    """Dialog to review undo actions."""
    def __init__(self, actions: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Undo Actions")
        self.resize(500, 300)
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("The following actions will be performed to undo the last run:"))
        
        self.list_widget = QListWidget()
        for action in actions:
            act_type = action.get("type", "unknown")
            item_id = action.get("id", "")
            summary = f"{act_type}: {item_id}"
            
            if act_type == "update_task":
                 summary += f" (Restoring original values)"
            
            self.list_widget.addItem(summary)
            
        layout.addWidget(self.list_widget)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)


class ResultsWidget(QWidget):
    """Widget to display execution results."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Status", "Action", "Message"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setShowGrid(False) # Cleaner look
        self.results_table.setAlternatingRowColors(True)
        
        self.layout.addWidget(self.results_table)

    def display_results(self, results: List[Dict[str, Any]], action_model: ActionModel = None):
        """Populate the results table."""
        self.results_table.setRowCount(0)
        self.results_table.setRowCount(len(results))
        
        for i, res in enumerate(results):
            # Status
            status_text = res.get("status", "unknown")
            status_item = QTableWidgetItem(status_text)
            
            # Simple color coding for status - could be moved to theme logic if we want strict separation
            if res.get("success"):
                status_item.setForeground(QColor("green"))
            else:
                status_item.setForeground(QColor("red"))
            
            if status_text == "simulated":
                 status_item.setForeground(QColor("orange"))

            self.results_table.setItem(i, 0, status_item)
            
            # Action Summary
            action = res.get("action", {})
            if action_model:
                summary = action_model._get_summary(action)
            else:
                summary = f"{action.get('type')} {action.get('id')}"
            self.results_table.setItem(i, 1, QTableWidgetItem(summary))
            
            # Message
            msg = res.get("message", "")
            self.results_table.setItem(i, 2, QTableWidgetItem(str(msg)))


class ActionsWidget(QWidget):
    """Widget for managing and executing proposed actions."""
    
    status_message = Signal(str) # To update main window status bar
    execution_finished = Signal(object, bool) # results, is_dry_run
    undo_finished = Signal(object) # results
    busy_state_changed = Signal(bool)

    def __init__(self, architect, threadpool: QThreadPool, parent=None):
        super().__init__(parent)
        self.architect = architect
        self.threadpool = threadpool
        self.action_model = ActionModel()
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Action Toolbar
        action_toolbar = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_none = QPushButton("Select None")
        self.btn_select_all.clicked.connect(lambda: self.action_model.select_all(True))
        self.btn_select_none.clicked.connect(lambda: self.action_model.select_all(False))
        
        action_toolbar.addWidget(self.btn_select_all)
        action_toolbar.addWidget(self.btn_select_none)
        action_toolbar.addStretch()
        
        # Undo Button
        self.undo_btn = QPushButton("Undo Last Run")
        self.undo_btn.setObjectName("DestructiveButton") # Apply specific style
        self.undo_btn.setEnabled(False) 
        self.undo_btn.clicked.connect(self.start_undo)
        action_toolbar.addWidget(self.undo_btn)
        
        # Dry Run Checkbox
        self.chk_dry_run = QCheckBox("Dry Run (simulate only)")
        self.chk_dry_run.setChecked(False)
        action_toolbar.addWidget(self.chk_dry_run)
        
        layout.addLayout(action_toolbar)

        # Action Table
        self.actions_view = QTableView()
        self.actions_view.setModel(self.action_model)
        self.actions_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.actions_view.setAlternatingRowColors(True)
        self.actions_view.verticalHeader().setVisible(False)
        self.actions_view.setShowGrid(False)
        
        header = self.actions_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.actions_view)

        # Buttons
        btn_layout = QHBoxLayout()
        self.execute_btn = QPushButton("Execute Selected Actions")
        self.execute_btn.setObjectName("PrimaryButton") 
        self.execute_btn.setEnabled(False) 
        self.execute_btn.clicked.connect(self.start_execute)
        
        self.copy_btn = QPushButton("Copy JSON")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self.copy_actions_to_clipboard)
        
        btn_layout.addWidget(self.execute_btn)
        btn_layout.addWidget(self.copy_btn)
        layout.addLayout(btn_layout)

    def set_actions(self, actions: List[Dict[str, Any]]):
        self.action_model.set_actions(actions)
        has_actions = len(actions) > 0
        self.execute_btn.setEnabled(has_actions)
        self.copy_btn.setEnabled(has_actions)
        self.btn_select_all.setEnabled(has_actions)
        self.btn_select_none.setEnabled(has_actions)
        self.update_undo_state()

    def update_undo_state(self):
        if self.architect.get_undo_actions():
            self.undo_btn.setEnabled(True)
        else:
            self.undo_btn.setEnabled(False)

    def set_ui_busy(self, busy: bool):
        self.execute_btn.setEnabled(not busy and self.action_model.rowCount() > 0)
        self.btn_select_all.setEnabled(not busy)
        self.btn_select_none.setEnabled(not busy)
        self.undo_btn.setEnabled(not busy and bool(self.architect.get_undo_actions()))
        self.actions_view.setEnabled(not busy)
        self.busy_state_changed.emit(busy)

    @Slot()
    def start_execute(self):
        actions_to_run = self.action_model.get_checked_actions()
        if not actions_to_run:
            self.status_message.emit("No actions selected.")
            return

        if self.action_model.has_destructive_selected():
            destructive_count = sum(1 for a in actions_to_run if a.get("type") in ["close_task", "delete_task", "remove_label", "delete_project"])
            reply = QMessageBox.question(
                self, 
                "Confirm Destructive Actions", 
                f"You are about to run {destructive_count} destructive action(s).\n\nAre you sure you want to continue?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                self.status_message.emit("Execution cancelled.")
                return

        is_dry_run = self.chk_dry_run.isChecked()
        self.status_message.emit(f"{'Simulating' if is_dry_run else 'Executing'} {len(actions_to_run)} actions...")
        self.set_ui_busy(True)
        
        worker = Worker(self.architect.execute, actions_to_run, dry_run=is_dry_run) 
        worker.signals.finished.connect(lambda r: self.on_execute_finished(r, is_dry_run))
        worker.signals.failed.connect(self.on_worker_error)
        worker.signals.finished.connect(lambda: self.set_ui_busy(False))
        worker.signals.failed.connect(lambda: self.set_ui_busy(False))
        self.threadpool.start(worker)

    def on_execute_finished(self, results, dry_run):
        self.execution_finished.emit(results, dry_run)
        if not dry_run:
             success_count = sum(1 for r in results if r.get("success"))
             if success_count > 0:
                 self.action_model.set_actions([])
                 self.execute_btn.setEnabled(False)
                 
             self.update_undo_state()

    @Slot()
    def start_undo(self):
        undo_actions = self.architect.get_undo_actions()
        if not undo_actions:
            self.status_message.emit("No actions to undo.")
            return
            
        dlg = UndoDialog(undo_actions, self)
        if dlg.exec() != QDialog.Accepted:
            return
            
        self.status_message.emit("Undoing last run...")
        self.set_ui_busy(True)
        
        worker = Worker(self.architect.perform_undo)
        worker.signals.finished.connect(self.on_undo_finished_internal)
        worker.signals.failed.connect(self.on_worker_error)
        worker.signals.finished.connect(lambda: self.set_ui_busy(False))
        worker.signals.failed.connect(lambda: self.set_ui_busy(False))
        self.threadpool.start(worker)

    def on_undo_finished_internal(self, results):
        self.undo_finished.emit(results)
        self.update_undo_state()

    @Slot(object)
    def on_worker_error(self, e):
        self.status_message.emit(f"Error: {e}")

    @Slot()
    def copy_actions_to_clipboard(self):
        actions = self.action_model.get_checked_actions() or self.action_model._actions
        if not actions:
            return
        
        try:
            json_str = json.dumps(actions, indent=2)
            QApplication.clipboard().setText(json_str)
            self.status_message.emit("Actions copied to clipboard!")
        except Exception as e:
            self.status_message.emit(f"Failed to copy: {e}")


class CoachPanel(QWidget):
    """Widget to display AI Coach thoughts/insights."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Use card styling for coach panel
        self.container = QFrame()
        self.container.setObjectName("Card")
        inner_layout = QVBoxLayout(self.container)
        inner_layout.setContentsMargins(Spacing.M, Spacing.M, Spacing.M, Spacing.M)
        
        header = QLabel("Coach Insight")
        header.setObjectName("SectionTitle")
        inner_layout.addWidget(header)
        
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlaceholderText("Ask the coach for advice on this step...")
        self.text_area.setFixedHeight(120) 
        self.text_area.setFrameShape(QFrame.NoFrame) # Let the card be the frame
        inner_layout.addWidget(self.text_area)
        
        self.layout.addWidget(self.container)
        
    def set_thought(self, thought: str):
        self.text_area.setHtml(thought) # Allow HTML formatting in thoughts
        
    def clear(self):
        self.text_area.clear()
