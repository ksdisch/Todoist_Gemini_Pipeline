from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QFrame, QVBoxLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from app.ui.theme.tokens import Spacing, FontSize
from app.ui.theme.manager import theme_manager

class HeaderWidget(QFrame):
    """
    App Header with Title, Session Info, and Global Actions.
    """
    refresh_clicked = Signal()
    theme_toggled = Signal()

    def __init__(self, parent=None):
        print("DEBUG: HeaderWidget.__init__")
        super().__init__(parent)
        self.setObjectName("Header")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.M, Spacing.S, Spacing.M, Spacing.S)
        layout.setSpacing(Spacing.M)

        # Title
        self.title_label = QLabel("Todoist Gemini Controller")
        self.title_label.setObjectName("SectionTitle") # Reusing SectionTitle for now, or define AppTitle
        # Override font size for app title
        font = self.title_label.font()
        font.setPointSizeF(16)
        font.setBold(True)
        self.title_label.setFont(font)
        
        layout.addWidget(self.title_label)

        # Spacer
        layout.addStretch()

        # Session Status (Text will be updated by controller)
        self.session_label = QLabel("Not Connected")
        self.session_label.setObjectName("SessionInfo")
        layout.addWidget(self.session_label)

        # Actions
        self.refresh_btn = QPushButton("Refresh State")
        self.refresh_btn.setToolTip("Fetch latest data from Todoist")
        self.refresh_btn.clicked.connect(self.refresh_clicked)
        layout.addWidget(self.refresh_btn)

        self.theme_btn = QPushButton("Toggle Theme")
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

    def set_session_info(self, text: str):
        self.session_label.setText(text)

    def _toggle_theme(self):
        new_mode = theme_manager.toggle_theme()
        # label text could update if we wanted "Switch to Light", but "Toggle Theme" is fine
        self.theme_toggled.emit()
