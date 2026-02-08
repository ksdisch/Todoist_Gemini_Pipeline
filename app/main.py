#!/usr/bin/env python3
import sys
import os

# Ensure the project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication
from app.gui.main_window import MainWindow
from app.ui.theme.manager import theme_manager

def main():
    app = QApplication(sys.argv)
    
    # Initialize Theme System (default to dark for "modern" feel)
    theme_manager.initialize(app, mode="dark")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
