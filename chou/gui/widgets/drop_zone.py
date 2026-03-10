"""
Drag-and-drop zone widget for adding PDF files
"""

from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QFrame


class DropZone(QLabel):
    """
    Label widget that accepts drag-and-drop PDF files and folders.
    Emits files_dropped signal with list of PDF paths.
    """

    files_dropped = Signal(list)  # List[Path]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(80)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setText(
            "Drag & Drop PDF files or folders here\n"
            "or use the toolbar buttons to add files"
        )
        self.setStyleSheet(
            "QLabel { border: 2px dashed palette(mid); "
            "border-radius: 8px; padding: 16px; }"
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        pass

    def dropEvent(self, event):
        pdf_paths: List[Path] = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() == '.pdf':
                pdf_paths.append(path)
            elif path.is_dir():
                pdf_paths.extend(path.glob('*.pdf'))

        if pdf_paths:
            self.files_dropped.emit(pdf_paths)
