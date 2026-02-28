"""
Preview table widget with editable cells
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableView, QHeaderView, QAbstractItemView


class PreviewTable(QTableView):
    """
    Table view for displaying and editing paper metadata.
    Columns: Status, Original, Title (editable), Authors (editable), Year (editable), New Filename
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # Selection
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setAlternatingRowColors(True)

        # Editing
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )

        # Header
        h = self.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.Interactive)

        self.verticalHeader().setDefaultSectionSize(28)
        self.verticalHeader().setVisible(False)

        # Sorting
        self.setSortingEnabled(False)

    def apply_column_widths(self):
        """Set sensible default column widths after model is attached"""
        h = self.horizontalHeader()
        if self.model() and self.model().columnCount() >= 6:
            h.resizeSection(0, 50)    # Status
            h.resizeSection(1, 200)   # Original
            h.resizeSection(2, 250)   # Title
            h.resizeSection(3, 180)   # Authors
            h.resizeSection(4, 55)    # Year
            # col 5 (New Filename) stretches
