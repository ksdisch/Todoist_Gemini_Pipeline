from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, 
    QStackedWidget, QSplitter, QLabel, QListWidget, QTextEdit, 
    QGroupBox, QLineEdit, QTabWidget, QMessageBox
)
from PySide6.QtCore import Qt, Slot, Signal, QThreadPool
from PySide6.QtGui import QColor

from app.core.orchestrator import Architect
from app.core.weekly_review import engine, planner, coach
from app.gui.widgets import ActionsWidget, ResultsWidget, CoachPanel
from app.gui.worker import Worker
from app.gui.history_widget import HistoryWidget, SessionSummaryWidget

class WeeklyReviewTab(QWidget):
    """
    Main widget for the Weekly Review feature.
    Connects to the Weekly Review Engine and manages the review session.
    """
    
    # Signals to communicate with MainWindow if needed (e.g. status updates)
    status_message = Signal(str)
    
    def __init__(self, architect: Architect, threadpool: QThreadPool, parent=None):
        super().__init__(parent)
        self.architect = architect
        self.threadpool = threadpool
        
        self.current_session = None
        self.current_state = None  # Todoist State (tasks/projects)
        self.step_viewmodels = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self) # Changed to QV to hold stack
        main_layout.setContentsMargins(0,0,0,0)
        
        self.main_stack = QStackedWidget()
        main_layout.addWidget(self.main_stack)
        
        # --- Page 0: Active Review Interface (Splitter) ---
        self.review_page = QWidget()
        review_layout = QHBoxLayout(self.review_page)
        review_layout.setContentsMargins(0,0,0,0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        review_layout.addWidget(self.splitter)
        
        # Add page 0
        self.main_stack.addWidget(self.review_page)
        
        # --- Left Pane: Steps & Progress ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        left_layout.addWidget(QLabel("<b>Review Steps</b>"))
        self.step_list = QListWidget()
        self.step_list.setEnabled(False) # Controlled by engine, not clickable directly usually
        # Populate initial steps from engine metadata (if static)
        for step in engine.STEPS:
            self.step_list.addItem(f"{step.order}. {step.title}")
            
        left_layout.addWidget(self.step_list)
        
        # Session Controls
        self.btn_start = QPushButton("Start New Review")
        self.btn_start.clicked.connect(self.start_session)
        left_layout.addWidget(self.btn_start)
        
        self.btn_history = QPushButton("View History")
        self.btn_history.clicked.connect(self.show_history)
        left_layout.addWidget(self.btn_history)
        
        left_layout.addStretch()
        self.splitter.addWidget(left_widget)
        
        # --- Center Pane: Workspace ---
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        
        # Step Title & Description
        self.lbl_step_title = QLabel("<h2>Welcome</h2>")
        self.lbl_step_desc = QLabel("Start a session to begin your weekly review.")
        self.lbl_step_desc.setWordWrap(True)
        center_layout.addWidget(self.lbl_step_title)
        center_layout.addWidget(self.lbl_step_desc)
        
        # Dynamic Content Area
        self.content_area = QStackedWidget()
        
        # 1. Default/Empty View
        self.view_empty = QLabel("No active step.")
        self.view_empty.setAlignment(Qt.AlignCenter)
        self.content_area.addWidget(self.view_empty)
        
        # 2. Text/Info View (Generic)
        self.view_generic = QTextEdit()
        self.view_generic.setReadOnly(True)
        self.content_area.addWidget(self.view_generic)
        
        # 3. Active Honesty View
        self.view_issues = QTextEdit()
        self.view_issues.setReadOnly(True) 
        self.content_area.addWidget(self.view_issues)
        
        # 4. Plan Next Week View (Complex Layout)
        self.view_plan_container = QWidget()
        vpc_layout = QVBoxLayout(self.view_plan_container)
        
        self.view_plan_report = QTextEdit()
        self.view_plan_report.setReadOnly(True)
        vpc_layout.addWidget(self.view_plan_report)
        
        # Controls for writing back to Todoist
        self.grp_plan_actions = QGroupBox("Apply Plan to Todoist")
        gpa_layout = QVBoxLayout(self.grp_plan_actions)
        
        # Priority
        self.chk_priority = QCheckBox("Set Priority on Selected Tasks (Ensure P2/Orange)")
        gpa_layout.addWidget(self.chk_priority)
        
        # Label
        lbl_layout = QHBoxLayout()
        self.chk_label = QCheckBox("Add Label:")
        self.chk_label.setChecked(False)
        self.input_label = QLineEdit("this_week")
        self.input_label.setPlaceholderText("Label name")
        lbl_layout.addWidget(self.chk_label)
        lbl_layout.addWidget(self.input_label)
        gpa_layout.addLayout(lbl_layout)
        
        # Comment
        cmt_layout = QHBoxLayout()
        self.chk_comment = QCheckBox("Add Comment:")
        self.chk_comment.setChecked(False)
        self.input_comment = QLineEdit("Weekly Plan")
        self.input_comment.setPlaceholderText("Comment text")
        cmt_layout.addWidget(self.chk_comment)
        cmt_layout.addWidget(self.input_comment)
        gpa_layout.addLayout(cmt_layout)
        
        self.btn_gen_plan_actions = QPushButton("Generate Plan Actions")
        self.btn_gen_plan_actions.clicked.connect(self.on_generate_plan_actions)
        gpa_layout.addWidget(self.btn_gen_plan_actions)
        
        vpc_layout.addWidget(self.grp_plan_actions)
        
        self.content_area.addWidget(self.view_plan_container)
        
        center_layout.addWidget(self.content_area)
        
        # Navigation Buttons
        nav_layout = QHBoxLayout()
        self.btn_back = QPushButton("Back") # Not usually supported by engine linear flow, but maybe?
        self.btn_back.setEnabled(False)
        self.btn_next = QPushButton("Next / Complete Step")
        self.btn_next.setEnabled(False)
        self.btn_next.clicked.connect(self.advance_step)
        
        nav_layout.addWidget(self.btn_back)
        nav_layout.addStretch()
        
        self.btn_ask_coach = QPushButton("Ask Coach")
        self.btn_ask_coach.setEnabled(False) # Enabled when session active
        self.btn_ask_coach.clicked.connect(self.on_ask_coach_clicked)
        nav_layout.addWidget(self.btn_ask_coach)
        
        nav_layout.addWidget(self.btn_next)
        center_layout.addLayout(nav_layout)
        
        self.splitter.addWidget(center_widget)
        
        # --- Right Pane: Actions & Results ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.actions_tabs = QTabWidget()
        
        # Use our reusable widgets!
        self.coach_panel = CoachPanel()
        right_layout.addWidget(self.coach_panel)
        
        self.actions_component = ActionsWidget(self.architect, self.threadpool)
        self.results_component = ResultsWidget()
        
        # Connect signals
        self.actions_component.status_message.connect(self.status_message)
        # We might want to refresh the step view if actions are executed (e.g. closing tasks)
        self.actions_component.execution_finished.connect(self.on_action_execution)
        self.actions_component.undo_finished.connect(self.on_action_execution) # Refresh on undo too
        
        self.actions_tabs.addTab(self.actions_component, "Proposed Actions")
        self.actions_tabs.addTab(self.results_component, "Results")
        
        right_layout.addWidget(self.actions_tabs)
        self.splitter.addWidget(right_widget)
        
        # Sizing
        self.splitter.setSizes([200, 500, 400])
        
        # --- Page 1: History List ---
        self.history_widget = HistoryWidget(self.threadpool)
        self.history_widget.session_selected.connect(self.show_session_detail)
        # We need a 'Back' button in history widget? It has Refresh. 
        # Actually, let's add a "Back to Start" button to history widget if accessed from here?
        # Or just use the tab bar if we had one.
        # Let's add a manual back button to the history_widget layout?
        # Or wrap it.
        # I'll modify history_widget setup in WeeklyReviewTab to add a back button at the top/bottom.
        # Wait, I can't easily modify the internal layout of HistoryWidget without inheriting or modifying the class.
        # Simpler: Add 'Back' button to main layout of HistoryWidget in `history_widget.py`.
        # For now, I'll rely on a "Back" button I'll inject *above* it?
        
        history_container = QWidget()
        hc_layout = QVBoxLayout(history_container)
        self.btn_hist_back = QPushButton("← Back to Review")
        self.btn_hist_back.clicked.connect(self.back_to_main)
        hc_layout.addWidget(self.btn_hist_back)
        hc_layout.addWidget(self.history_widget)
        
        self.main_stack.addWidget(history_container)
        
        # --- Page 2: Session Detail ---
        self.summary_widget = SessionSummaryWidget(self.threadpool)
        self.summary_widget.close_requested.connect(self.close_history_detail)
        self.main_stack.addWidget(self.summary_widget)
        
    @Slot()
    def show_history(self):
        self.history_widget.load_history()
        self.main_stack.setCurrentWidget(self.main_stack.widget(1)) # history_container
        
    @Slot(str)
    def show_session_detail(self, session_id):
        self.summary_widget.load_session(session_id)
        self.main_stack.setCurrentWidget(self.summary_widget)
        
    @Slot()
    def close_history_detail(self):
        self.main_stack.setCurrentWidget(self.main_stack.widget(1)) # history_container
        
    @Slot()
    def back_to_main(self):
        self.main_stack.setCurrentWidget(self.review_page)

    def set_current_state(self, state):
        """Receive updated Todoist state from MainWindow."""
        self.current_state = state
        # If we have an active session, maybe refresh the current step view?
        if self.current_session:
            self.refresh_current_step()

    @Slot()
    def start_session(self):
        if not self.current_state:
            QMessageBox.warning(self, "No State", "Please refresh Todoist state first.")
            return

        self.status_message.emit("Starting Review Session...")
        
        # Run engine.start_session in worker? It's fast (local), but good practice.
        # But engine calls persistence which is file I/O.
        # Let's run in thread.
        worker = Worker(engine.start_session, self.current_state)
        worker.signals.finished.connect(self.on_session_started)
        worker.signals.failed.connect(lambda e: self.status_message.emit(f"Error starting session: {e}"))
        self.threadpool.start(worker)

    @Slot(object)
    def on_session_started(self, session):
        self.current_session = session
        self.status_message.emit("Review Session Started.")
        self.btn_start.setEnabled(False)
        self.btn_next.setEnabled(True)
        self.btn_ask_coach.setEnabled(True)
        self.refresh_current_step()

    def refresh_current_step(self):
        if not self.current_session or not self.current_session.current_step_id:
            return
            
        step_id = self.current_session.current_step_id
        
        # Highlight step in list
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            # Assumption: order maps to index
            if engine.STEPS[i].id == step_id:
                 item.setBackground(QColor("#d3d3d3")) # Highlight
                 item.setForeground(QColor("black"))
            else:
                 item.setBackground(Qt.NoBrush)
                 # Check if completed?
                 # logic to check completed steps in session.completed_steps
                 if any(cs.step_id == engine.STEPS[i].id for cs in self.current_session.completed_steps):
                     item.setForeground(QColor("green"))
                 else:
                     item.setForeground(Qt.black)

        # Get ViewModel
        worker = Worker(engine.get_step_viewmodel, step_id, self.current_state, self.current_session)
        worker.signals.finished.connect(self.render_step)
        worker.signals.failed.connect(lambda e: self.status_message.emit(f"Error getting step: {e}"))
        self.threadpool.start(worker)

    @Slot(object)
    def render_step(self, vm):
        step = vm["step"]
        context = vm.get("context", {})
        
        self.lbl_step_title.setText(f"<h2>{step.title}</h2>")
        self.lbl_step_desc.setText(step.description)
        
        # Switch content based on step_id
        if step.id == "active_honesty":
            self.content_area.setCurrentWidget(self.view_issues)
            # Render issues
            html = "<h3>Issues Found:</h3>"
            issues = context.get("issues", []) + context.get("integrity_issues", []) + context.get("waiting_issues", [])
            if not issues:
                html += "<p style='color:green'>No issues found! Great job.</p>"
            else:
                html += "<ul>"
                for issue in issues:
                    html += f"<li><b>{issue.title}</b>: {issue.description}</li>"
                html += "</ul>"
            
            # Suggest Actions?
            # If the engine provided 'recommended_actions', we could populate ActionsWidget.
            # Currently the engine vm doesn't explicitly return actions in the simple view, 
            # but usually the user would 'generate' actions.
            # For now, let's just show issues.
            self.view_issues.setHtml(html)
            
        elif step.id == "plan_next_week":
            self.content_area.setCurrentWidget(self.view_plan_container)
            # Render coverage
            cov = context.get("area_coverage", [])
            html = "<h3>Area Coverage</h3><ul>"
            for c in cov:
                # Assuming c is AreaCoverage object or dict? Dict likely if from worker return? 
                # Worker returns object if engine returns object. Engine returns Dict[str, Any] which contains objects.
                # PySide signals pass objects fine.
                color = "red" if c.status != "ok" else "green"
                html += f"<li><b>{c.area_name}</b>: {c.selected_count}/{c.required_min_touches} (Status: <span style='color:{color}'>{c.status}</span>)</li>"
            html += "</ul>"
            self.view_plan_report.setHtml(html)
            
            # Update Comment Default Date
            today = datetime.now().strftime("%Y-%m-%d")
            self.input_comment.setText(f"Weekly Plan {today}")
            
        else:
            self.content_area.setCurrentWidget(self.view_generic)
            note = context.get("note", "")
            self.view_generic.setHtml(f"<i>{note}</i>" if note else "")

    @Slot()
    def advance_step(self):
        # 1. Validate
        step_id = self.current_session.current_step_id
        worker = Worker(engine.validate_step, step_id, self.current_state, self.current_session)
        worker.signals.finished.connect(self.on_validate_finished)
        self.threadpool.start(worker)
        
    @Slot(object)
    def on_validate_finished(self, issues):
        if issues:
            # Block or Warn?
            # For now, Warn and allow proceed if user insists? 
            # Or just show them.
            msg = f"There are {len(issues)} unresolved issues.\n\n"
            msg += "\n".join([f"- {i.title}" for i in issues[:5]])
            if len(issues) > 5: msg += "\n..."
            
            reply = QMessageBox.question(self, "Unresolved Issues", msg + "\n\nProceed anyway?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return

        # 2. Complete Step
        # Gather inputs? For now we send empty dict or simple inputs.
        user_inputs = {}
        
        worker = Worker(engine.complete_step, self.current_session.current_step_id, self.current_session, user_inputs, self.current_state)
        worker.signals.finished.connect(self.on_step_completed)
        self.threadpool.start(worker)

    @Slot(object)
    def on_step_completed(self, result):
        # 3. Advance local session state
        # The engine updates the session object in place (and saves it).
        # We need to refresh our local view of the session or just rely on the fact that 'session' object is shared/mutable?
        # Engine 'complete_step' returns StepResult. It modifies session.current_step_id.
        
        if self.current_session.status == "completed":
            QMessageBox.information(self, "Review Complete", "You returned to the Shire!")
            self.status_message.emit("Session complete.")
            self.btn_next.setEnabled(False)
            self.btn_start.setEnabled(True)
            # Maybe reset UI?
        else:
            self.refresh_current_step()

    @Slot(object, bool)
    def on_action_execution(self, results, dry_run=False):
        # Access results from child? It is passed.
        # If we executed real actions, we should refresh the main state.
        if not dry_run:
            # We need to signal MainWindow to refresh state?
            # Or we can accept that MainWindow handles its own refresh?
            # Ideally, WeeklyReviewTab should emit "state_refresh_needed".
            pass
        
        # Also refresh step view
        self.refresh_current_step()

    @Slot()
    def on_ask_coach_clicked(self):
        if not self.current_session or not self.current_state:
            return
            
        step_id = self.current_session.current_step_id
        
        self.status_message.emit("Consulting the Coach... (this may take a moment)")
        self.coach_panel.set_thought("Thinking...")
        self.btn_ask_coach.setEnabled(False)
        self.actions_component.set_ui_busy(True)
        
        worker = Worker(
            coach.analyze_step, 
            self.architect, 
            step_id, 
            self.current_state, 
            self.current_session, 
            None # profile
        )
        worker.signals.finished.connect(self.on_coach_finished)
        worker.signals.failed.connect(self.on_coach_failed)
        self.threadpool.start(worker)
        
    @Slot(object)
    def on_coach_finished(self, result):
        self.btn_ask_coach.setEnabled(True)
        self.actions_component.set_ui_busy(False)
        
        thought = result.get("thought", "")
        actions = result.get("actions", [])
        
        self.coach_panel.set_thought(thought)
        self.actions_component.set_actions(actions)
        self.status_message.emit(f"Coach proposed {len(actions)} actions.")
        
    @Slot(object)
    def on_coach_failed(self, e):
        self.btn_ask_coach.setEnabled(True)
        self.actions_component.set_ui_busy(False)
        self.coach_panel.set_thought(f"Error: {str(e)}")
        self.status_message.emit(f"Coach error: {e}")

    @Slot()
    def on_generate_plan_actions(self):
        if not self.current_session or not self.current_session.plan_draft:
            self.status_message.emit("No active plan draft to apply.")
            return

        options = {
            "set_priorities": self.chk_priority.isChecked(),
            "add_label": self.input_label.text() if self.chk_label.isChecked() else None,
            "add_comment": self.input_comment.text() if self.chk_comment.isChecked() else None
        }

        # Use the planner to generate actions based on the draft and options
        actions = planner.generate_plan_application_actions(self.current_session.plan_draft, options)

        if not actions:
            QMessageBox.information(self, "No Actions", "No actions generated. Ensure tasks are selected in the plan.")
            return

        self.actions_component.set_actions(actions)
        self.status_message.emit(f"Generated {len(actions)} plan application actions.")
        self.actions_tabs.setCurrentWidget(self.actions_component)
