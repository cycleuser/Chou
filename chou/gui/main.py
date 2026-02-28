"""
Chou GUI entry point
"""

import sys


def main():
    """Launch the Chou GUI application"""
    from PySide6.QtWidgets import QApplication
    from .main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("chou")
    app.setOrganizationName("cycleuser")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
