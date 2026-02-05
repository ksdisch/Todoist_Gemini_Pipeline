from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QPushButton, QLabel, QHeaderView, QSplitter, QTextEdit, QGroupBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor

from app.gui.worker import Worker
from app.core.weekly_review import persistence

class HistoryWidget(QWidget):
    """
    Displays a list of past Weekly Review sessions.
    Allows drilling down into a specific session summary.
    """
    
    session_selected = Signal(str) # Emits session_id
    
    def __init__(self, threadpool):
        super().__init__()
        self.threadpool = threadpool
        self.sessions_data = []
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header / Controls
        ctrl_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh History")
        self.btn_refresh.clicked.connect(self.load_history)
        ctrl_layout.addWidget(QLabel("<h2>Past Reviews</h2>"))
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_refresh)
        layout.addLayout(ctrl_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Date", "Status", "Score", "Outcomes"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemDoubleClicked.connect(self.on_table_double_click)
        
        layout.addWidget(self.table)
        
        # Instructions
        layout.addWidget(QLabel("<i>Double-click a session to view details.</i>"))
        
    def load_history(self):
        self.btn_refresh.setEnabled(False)
        self.table.setRowCount(0)
        
        worker = Worker(persistence.list_sessions_metadata)
        worker.signals.finished.connect(self.on_history_loaded)
        worker.signals.failed.connect(self.on_history_failed)
        self.threadpool.start(worker)
        
    @Slot(object)
    def on_history_loaded(self, data: List[Dict]):
        self.sessions_data = data
        self.table.setRowCount(len(data))
        self.btn_refresh.setEnabled(True)
        
        for row, session in enumerate(data):
            # Date
            start_time = session.get("start_time")
            if isinstance(start_time, str):
                start_time_str = start_time[:10] # Simple parsing if string
            elif hasattr(start_time, 'strftime'):
                start_time_str = start_time.strftime("%Y-%m-%d %H:%M")
            else:
                start_time_str = "Unknown"
                
            self.table.setItem(row, 0, QTableWidgetItem(start_time_str))
            
            # Status
            status = session.get("status", "unknown")
            item_status = QTableWidgetItem(status)
            if status == "completed":
                item_status.setForeground(QColor("green"))
            self.table.setItem(row, 1, item_status)
            
            # Score
            score = session.get("total_score", 0)
            self.table.setItem(row, 2, QTableWidgetItem(str(score)))
            
            # Outcomes
            outcomes = session.get("outcomes", [])
            outcomes_str = ", ".join(outcomes) if outcomes else ""
            self.table.setItem(row, 3, QTableWidgetItem(outcomes_str))
            
            # Store ID in first item
            self.table.item(row, 0).setData(Qt.UserRole, session.get("id"))

    @Slot(object)
    def on_history_failed(self, e):
        self.btn_refresh.setEnabled(True)
        # Show error?
        print(f"Failed to load history: {e}")

    def on_table_double_click(self, item):
        row = item.row()
        session_id = self.table.item(row, 0).data(Qt.UserRole)
        if session_id:
            self.session_selected.emit(session_id)


class SessionSummaryWidget(QWidget):
    """
    Read-only detail view of a session.
    """
    
    close_requested = Signal()
    
    def __init__(self, threadpool):
        super().__init__()
        self.threadpool = threadpool
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        top_layout = QHBoxLayout()
        self.btn_close = QPushButton("Back to History")
        self.btn_close.clicked.connect(self.close_requested.emit)
        top_layout.addWidget(self.btn_close)
        top_layout.addStretch()
        layout.addLayout(top_layout)
        
        self.lbl_title = QLabel("<h2>Session Details</h2>")
        layout.addWidget(self.lbl_title)
        
        # Content
        self.content_area = QTextEdit()
        self.content_area.setReadOnly(True)
        layout.addWidget(self.content_area)
        
    def load_session(self, session_id):
        self.content_area.setText("Loading...")
        worker = Worker(persistence.load_session, session_id)
        worker.signals.finished.connect(self.render_session)
        worker.signals.failed.connect(lambda e: self.content_area.setText(f"Error: {e}"))
        self.threadpool.start(worker)
        
    @Slot(object)
    def render_session(self, session):
        if not session:
            self.content_area.setText("Session not found.")
            return

        # Build HTML report
        start_str = session.start_time.strftime("%Y-%m-%d %H:%M") if session.start_time else "?"
        end_str = session.completed_at.strftime("%Y-%m-%d %H:%M") if session.completed_at else "Not completed"
        
        html = f"<h3>Review Session: {start_str}</h3>"
        html += f"<p><b>Status:</b> {session.status}<br><b>Completed:</b> {end_str}</p>"
        
        # Scores
        total_score = sum(session.scores.values()) if session.scores else 0
        html += f"<h4>Total Score: {total_score} / 8 (approx)</h4>" # Assuming 4 steps * 2 points
        
        if session.scores:
            html += "<ul>"
            for step, score in session.scores.items():
                html += f"<li>{step}: {score}/2</li>"
            html += "</ul>"
            
        # Outcomes / Plan
        if session.plan_draft:
            html += "<h4>Outcomes / Priorities</h4>"
            if session.plan_draft.top_priorities:
                html += "<ul>"
                for p in session.plan_draft.top_priorities:
                    html += f"<li>{p}</li>"
                html += "</ul>"
            
            if session.plan_draft.focus_areas:
                html += "<h4>Focus Areas</h4>"
                html += "<p>" + ", ".join(session.plan_draft.focus_areas) + "</p>"
                
            if session.plan_draft.notes:
                html += "<h4>Notes</h4>"
                html += f"<pre>{session.plan_draft.notes}</pre>"
        
        self.content_area.setHtml(html)
