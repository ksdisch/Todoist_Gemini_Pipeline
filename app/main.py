#!/usr/bin/env python3
import sys
import os

# Ensure the project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication
from app.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Optional: Set a style or theme here
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
