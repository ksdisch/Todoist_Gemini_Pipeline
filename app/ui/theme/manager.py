from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from .tokens import Spacing, BorderRadius, FontSize
from .palette import Palette
import os

class ThemeManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance.current_mode = "light" # Default
            cls._instance.app = None
        return cls._instance

    def initialize(self, app: QApplication, mode: str = "light"):
        self.app = app
        self.app.setStyle("Fusion")
        self.apply_theme(mode)

    def toggle_theme(self):
        new_mode = "dark" if self.current_mode == "light" else "light"
        self.apply_theme(new_mode)
        return new_mode

    def apply_theme(self, mode: str):
        self.current_mode = mode
        palette_dict = Palette.DARK if mode == "dark" else Palette.LIGHT

        # 1. Apply QPalette (for Fusion style base)
        q_palette = QPalette()
        
        # Map common roles
        q_palette.setColor(QPalette.Window, QColor(palette_dict["window_bg"]))
        q_palette.setColor(QPalette.WindowText, QColor(palette_dict["text_primary"]))
        q_palette.setColor(QPalette.Base, QColor(palette_dict["surface_bg"]))
        q_palette.setColor(QPalette.AlternateBase, QColor(palette_dict["action_row_alt"]))
        q_palette.setColor(QPalette.ToolTipBase, QColor(palette_dict["surface_bg"]))
        q_palette.setColor(QPalette.ToolTipText, QColor(palette_dict["text_primary"]))
        q_palette.setColor(QPalette.Text, QColor(palette_dict["text_primary"]))
        q_palette.setColor(QPalette.Button, QColor(palette_dict["surface_bg"]))
        q_palette.setColor(QPalette.ButtonText, QColor(palette_dict["text_primary"]))
        q_palette.setColor(QPalette.BrightText, QColor(palette_dict["primary"]))
        q_palette.setColor(QPalette.Link, QColor(palette_dict["primary"]))
        q_palette.setColor(QPalette.Highlight, QColor(palette_dict["selection"]))
        q_palette.setColor(QPalette.HighlightedText, QColor(palette_dict["selection_text"]))
        
        # Disabled states (simple dimming)
        q_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(palette_dict["text_secondary"]))
        q_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(palette_dict["text_secondary"]))

        self.app.setPalette(q_palette)

        # 2. Load and process stylesheet
        try:
            current_dir = os.path.dirname(__file__)
            qss_path = os.path.join(current_dir, "styles.qss")
            with open(qss_path, "r") as f:
                qss_template = f.read()

            # Simple string replacement for tokens
            # In a real engine we might use Jinja2, but manual replacement is fine here
            processed_qss = self._process_qss(qss_template, palette_dict)
            self.app.setStyleSheet(processed_qss)
            
        except Exception as e:
            print(f"Failed to load theme styles: {e}")

    def _process_qss(self, template: str, palette: dict) -> str:
        # Replace Palette colors
        for key, value in palette.items():
            template = template.replace(f"{{{{palette.{key}}}}}", value)
        
        # Replace Tokens
        # Spacing
        for key, value in Spacing.__dict__.items():
            if not key.startswith("__"):
                template = template.replace(f"{{{{Spacing.{key}}}}}", str(value))
        
        # BorderRadius
        for key, value in BorderRadius.__dict__.items():
            if not key.startswith("__"):
                template = template.replace(f"{{{{BorderRadius.{key}}}}}", str(value))

        # FontSize
        for key, value in FontSize.__dict__.items():
            if not key.startswith("__"):
                template = template.replace(f"{{{{FontSize.{key}}}}}", str(value))
                
        return template

theme_manager = ThemeManager()
