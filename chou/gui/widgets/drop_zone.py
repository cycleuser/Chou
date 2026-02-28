"""
Drag-and-drop zone widget for adding PDF files
"""

from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget


class DropZone(QWidget):
    """
    Widget that accepts drag-and-drop PDF files and folders.
    Emits files_dropped signal with list of PDF paths.
    """

    files_dropped = Signal(list)  # List[Path]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self._hovering = False

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._hovering = True
            self.update()

    def dragLeaveEvent(self, event):
        self._hovering = False
        self.update()

    def dropEvent(self, event):
        self._hovering = False
        self.update()

        pdf_paths: List[Path] = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() == '.pdf':
                pdf_paths.append(path)
            elif path.is_dir():
                pdf_paths.extend(path.glob('*.pdf'))

        if pdf_paths:
            self.files_dropped.emit(pdf_paths)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(10, 10, -10, -10)

        # Background
        if self._hovering:
            painter.fillRect(rect, QColor(200, 220, 255, 100))
        else:
            painter.fillRect(rect, QColor(245, 245, 245))

        # Dashed border
        pen = QPen(QColor(150, 150, 150) if not self._hovering else QColor(80, 120, 200))
        pen.setStyle(Qt.DashLine)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 8, 8)

        # Text
        font = QFont()
        font.setPointSize(11)
        painter.setFont(font)
        painter.setPen(QColor(120, 120, 120) if not self._hovering else QColor(60, 90, 180))
        painter.drawText(rect, Qt.AlignCenter,
                         "Drag & Drop PDF files or folders here\n"
                         "or use the toolbar buttons to add files")
        painter.end()
