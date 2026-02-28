"""
Qt table model for paper data display and editing
"""

from typing import List, Optional, Any

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QIcon

from ...core.models import PaperInfo, Author, AuthorFormat
from ...core.processor import PaperProcessor
from ...core.author_parser import parse_all_authors

COLUMNS = ["Status", "Original Filename", "Title", "Authors", "Year", "New Filename"]
COL_STATUS = 0
COL_ORIGINAL = 1
COL_TITLE = 2
COL_AUTHORS = 3
COL_YEAR = 4
COL_NEW_FILENAME = 5


class PaperTableModel(QAbstractTableModel):
    """
    Table model wrapping List[PaperInfo] for QTableView.
    Supports editing of Title, Authors, and Year columns.
    """

    def __init__(self, processor: PaperProcessor, parent=None):
        super().__init__(parent)
        self._papers: List[PaperInfo] = []
        self._processor = processor

    @property
    def papers(self) -> List[PaperInfo]:
        return self._papers

    def set_processor(self, processor: PaperProcessor):
        self._processor = processor

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._papers)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._papers):
            return None

        paper = self._papers[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == COL_STATUS:
                status_map = {
                    "pending": "...",
                    "success": "OK",
                    "error": "ERR",
                    "skip": "SKIP",
                }
                return status_map.get(paper.status, paper.status)
            elif col == COL_ORIGINAL:
                return paper.original_filename
            elif col == COL_TITLE:
                return paper.title or ""
            elif col == COL_AUTHORS:
                return ", ".join(a.full_name for a in paper.authors)
            elif col == COL_YEAR:
                return str(paper.year) if paper.year else ""
            elif col == COL_NEW_FILENAME:
                return paper.new_filename or ""

        elif role == Qt.EditRole:
            if col == COL_TITLE:
                return paper.title or ""
            elif col == COL_AUTHORS:
                return ", ".join(a.full_name for a in paper.authors)
            elif col == COL_YEAR:
                return str(paper.year) if paper.year else ""

        elif role == Qt.BackgroundRole:
            if paper.status == "success":
                return QColor(220, 255, 220)
            elif paper.status == "error":
                return QColor(255, 220, 220)
            elif paper.status == "pending":
                return QColor(255, 255, 220)

        elif role == Qt.ToolTipRole:
            if col == COL_STATUS and paper.error_message:
                return paper.error_message
            elif col == COL_ORIGINAL:
                return str(paper.file_path)
            elif col == COL_NEW_FILENAME and paper.new_filename:
                return paper.new_filename

        elif role == Qt.TextAlignmentRole:
            if col in (COL_STATUS, COL_YEAR):
                return Qt.AlignCenter

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        base_flags = super().flags(index)
        col = index.column()
        if col in (COL_TITLE, COL_AUTHORS, COL_YEAR):
            return base_flags | Qt.ItemIsEditable
        return base_flags

    def setData(self, index: QModelIndex, value: Any, role=Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False

        paper = self._papers[index.row()]
        col = index.column()

        if col == COL_TITLE:
            paper.title = value.strip() if value else None
        elif col == COL_AUTHORS:
            if value and value.strip():
                paper.authors = parse_all_authors(value.strip())
            else:
                paper.authors = []
        elif col == COL_YEAR:
            try:
                paper.year = int(value) if value else None
            except ValueError:
                return False
        else:
            return False

        # Regenerate filename after edit
        self._processor.update_paper_filename(paper)

        # Emit change for the entire row
        left = self.index(index.row(), 0)
        right = self.index(index.row(), len(COLUMNS) - 1)
        self.dataChanged.emit(left, right)
        return True

    def add_papers(self, papers: List[PaperInfo]):
        """Add papers to the model"""
        if not papers:
            return
        start = len(self._papers)
        self.beginInsertRows(QModelIndex(), start, start + len(papers) - 1)
        self._papers.extend(papers)
        self.endInsertRows()

    def clear(self):
        """Remove all papers"""
        if not self._papers:
            return
        self.beginResetModel()
        self._papers.clear()
        self.endResetModel()

    def remove_row(self, row: int):
        """Remove a single row"""
        if 0 <= row < len(self._papers):
            self.beginRemoveRows(QModelIndex(), row, row)
            self._papers.pop(row)
            self.endRemoveRows()

    def get_paper(self, row: int) -> Optional[PaperInfo]:
        """Get PaperInfo at given row"""
        if 0 <= row < len(self._papers):
            return self._papers[row]
        return None

    def refresh_all(self):
        """Emit dataChanged for all rows"""
        if self._papers:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._papers) - 1, len(COLUMNS) - 1)
            self.dataChanged.emit(top_left, bottom_right)
