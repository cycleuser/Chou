"""
Main application window for Chou GUI
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QThread, Signal, QSettings
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QComboBox, QSpinBox, QCheckBox, QLabel, QSplitter,
    QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QProgressBar, QApplication,
)

from ..__version__ import __version__, __app_name__, __app_name_cn__
from ..core.models import AuthorFormat, PaperInfo
from ..core.processor import PaperProcessor
from .models.paper_model import PaperTableModel
from .widgets.drop_zone import DropZone
from .widgets.preview_table import PreviewTable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker thread for background processing
# ---------------------------------------------------------------------------

class ProcessWorker(QThread):
    """Background worker for PDF processing"""
    paper_ready = Signal(object)   # PaperInfo
    finished_all = Signal()

    def __init__(self, processor: PaperProcessor, pdf_paths: List[Path], parent=None):
        super().__init__(parent)
        self._processor = processor
        self._paths = pdf_paths

    def run(self):
        for path in self._paths:
            paper = self._processor.process_single(path)
            self.paper_ready.emit(paper)
        self.finished_all.emit()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

HISTORY_FILE = "chou_history.json"


class MainWindow(QMainWindow):
    """Chou main application window"""

    def __init__(self):
        super().__init__()
        self._settings = QSettings("cycleuser", "chou")

        # Processor
        self._processor = PaperProcessor()
        self._model = PaperTableModel(self._processor)
        self._worker: Optional[ProcessWorker] = None
        self._history: List[dict] = []

        self._init_ui()
        self._load_history()
        self._restore_geometry()

    # ---- UI construction ---------------------------------------------------

    def _init_ui(self):
        self.setWindowTitle(f"{__app_name__} ({__app_name_cn__}) v{__version__}")
        self.setMinimumSize(960, 600)

        # Menu bar
        self._create_menus()

        # Toolbar
        self._create_toolbar()

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Splitter: left (main) | right (history)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- Left panel ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Drop zone
        self._drop_zone = DropZone()
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        left_layout.addWidget(self._drop_zone)

        # Settings row
        settings_box = self._create_settings_box()
        left_layout.addWidget(settings_box)

        # Preview table
        self._table = PreviewTable()
        self._table.setModel(self._model)
        self._table.apply_column_widths()
        left_layout.addWidget(self._table, stretch=1)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        left_layout.addWidget(self._progress)

        splitter.addWidget(left)

        # --- Right panel: history ---
        history_widget = self._create_history_panel()
        splitter.addWidget(history_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._update_status()

    # ---- Menus -------------------------------------------------------------

    def _create_menus(self):
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        act_add_files = QAction("Add &Files...", self)
        act_add_files.setShortcut(QKeySequence("Ctrl+O"))
        act_add_files.triggered.connect(self._add_files)
        file_menu.addAction(act_add_files)

        act_add_folder = QAction("Add Fol&der...", self)
        act_add_folder.setShortcut(QKeySequence("Ctrl+D"))
        act_add_folder.triggered.connect(self._add_folder)
        file_menu.addAction(act_add_folder)

        file_menu.addSeparator()

        act_export = QAction("&Export CSV...", self)
        act_export.setShortcut(QKeySequence("Ctrl+E"))
        act_export.triggered.connect(self._export_csv)
        file_menu.addAction(act_export)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # Edit menu
        edit_menu = menu_bar.addMenu("&Edit")

        act_clear = QAction("&Clear List", self)
        act_clear.triggered.connect(self._clear_list)
        edit_menu.addAction(act_clear)

        act_remove = QAction("&Remove Selected", self)
        act_remove.setShortcut(QKeySequence.Delete)
        act_remove.triggered.connect(self._remove_selected)
        edit_menu.addAction(act_remove)

        # View menu
        view_menu = menu_bar.addMenu("&View")

        self._act_toggle_history = QAction("Show &History", self)
        self._act_toggle_history.setCheckable(True)
        self._act_toggle_history.setChecked(True)
        self._act_toggle_history.triggered.connect(self._toggle_history)
        view_menu.addAction(self._act_toggle_history)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        act_about = QAction("&About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # ---- Toolbar -----------------------------------------------------------

    def _create_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._btn_add_files = toolbar.addAction("Add Files")
        self._btn_add_files.triggered.connect(self._add_files)

        self._btn_add_folder = toolbar.addAction("Add Folder")
        self._btn_add_folder.triggered.connect(self._add_folder)

        toolbar.addSeparator()

        self._btn_process = toolbar.addAction("Process All")
        self._btn_process.triggered.connect(self._process_all)

        self._btn_rename = toolbar.addAction("Rename")
        self._btn_rename.triggered.connect(self._apply_rename)

        toolbar.addSeparator()

        self._btn_clear = toolbar.addAction("Clear")
        self._btn_clear.triggered.connect(self._clear_list)

    # ---- Settings box ------------------------------------------------------

    def _create_settings_box(self) -> QGroupBox:
        box = QGroupBox("Settings")
        layout = QFormLayout(box)
        layout.setContentsMargins(8, 4, 8, 4)

        row = QHBoxLayout()

        # Format combo
        self._combo_format = QComboBox()
        for fmt in AuthorFormat:
            self._combo_format.addItem(fmt.value, fmt)
        self._combo_format.currentIndexChanged.connect(self._on_settings_changed)
        row.addWidget(QLabel("Format:"))
        row.addWidget(self._combo_format)

        row.addSpacing(12)

        # N authors
        self._spin_n = QSpinBox()
        self._spin_n.setRange(1, 20)
        self._spin_n.setValue(3)
        self._spin_n.valueChanged.connect(self._on_settings_changed)
        row.addWidget(QLabel("N:"))
        row.addWidget(self._spin_n)

        row.addSpacing(12)

        # Recursive
        self._chk_recursive = QCheckBox("Recursive")
        row.addWidget(self._chk_recursive)

        row.addStretch()

        layout.addRow(row)
        return box

    # ---- History panel -----------------------------------------------------

    def _create_history_panel(self) -> QWidget:
        self._history_widget = QGroupBox("History")
        layout = QVBoxLayout(self._history_widget)

        self._history_list = QListWidget()
        self._history_list.setAlternatingRowColors(True)
        layout.addWidget(self._history_list)

        return self._history_widget

    # ---- Actions -----------------------------------------------------------

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if files:
            paths = [Path(f) for f in files]
            self._start_processing(paths)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            folder_path = Path(folder)
            recursive = self._chk_recursive.isChecked()
            if recursive:
                pdfs = list(folder_path.rglob('*.pdf'))
            else:
                pdfs = list(folder_path.glob('*.pdf'))
            if pdfs:
                self._start_processing(pdfs)
            else:
                QMessageBox.information(self, "No PDFs", "No PDF files found in the selected folder.")

    def _process_all(self):
        """Re-process all papers currently in the table"""
        papers = self._model.papers
        if not papers:
            return
        paths = [p.file_path for p in papers]
        self._model.clear()
        self._start_processing(paths)

    def _start_processing(self, paths: List[Path]):
        """Launch background worker to process PDFs"""
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "Processing is already running.")
            return

        self._rebuild_processor()

        self._progress.setMaximum(len(paths))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._set_ui_busy(True)

        self._worker = ProcessWorker(self._processor, paths)
        self._worker.paper_ready.connect(self._on_paper_ready)
        self._worker.finished_all.connect(self._on_processing_done)
        self._worker.start()

    def _on_paper_ready(self, paper: PaperInfo):
        self._model.add_papers([paper])
        self._progress.setValue(self._progress.value() + 1)
        self._update_status()

    def _on_processing_done(self):
        self._progress.setVisible(False)
        self._set_ui_busy(False)
        self._update_status()

    def _apply_rename(self):
        papers = self._model.papers
        if not papers:
            return

        success = [p for p in papers if p.status == "success" and p.new_filename]
        if not success:
            QMessageBox.information(self, "Nothing to Rename",
                                    "No papers with valid new filenames.")
            return

        reply = QMessageBox.question(
            self, "Confirm Rename",
            f"Rename {len(success)} file(s)?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._processor.apply_renames(papers, dry_run=False)
        self._model.refresh_all()
        self._update_status()
        self._add_history_entry(papers)

    def _clear_list(self):
        self._model.clear()
        self._update_status()

    def _remove_selected(self):
        rows = sorted(set(idx.row() for idx in self._table.selectedIndexes()), reverse=True)
        for row in rows:
            self._model.remove_row(row)
        self._update_status()

    def _export_csv(self):
        if not self._model.papers:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "chou_results.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        import csv
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Original", "New", "Title", "Authors", "Year", "Status", "Error"])
            for p in self._model.papers:
                writer.writerow([
                    p.original_filename,
                    p.new_filename or "",
                    p.title or "",
                    ", ".join(a.full_name for a in p.authors),
                    p.year or "",
                    p.status,
                    p.error_message or "",
                ])
        self._status.showMessage(f"Exported to {path}", 5000)

    # ---- Settings sync -----------------------------------------------------

    def _on_settings_changed(self):
        self._rebuild_processor()
        # Re-generate filenames for all existing papers
        for paper in self._model.papers:
            if paper.title and paper.authors and paper.year:
                self._processor.update_paper_filename(paper)
        self._model.refresh_all()

    def _rebuild_processor(self):
        fmt = self._combo_format.currentData()
        n = self._spin_n.value()
        self._processor = PaperProcessor(author_format=fmt, n_authors=n)
        self._model.set_processor(self._processor)

    # ---- History -----------------------------------------------------------

    def _add_history_entry(self, papers: List[PaperInfo]):
        from datetime import datetime
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "count": len([p for p in papers if p.status == "success"]),
            "total": len(papers),
        }
        self._history.insert(0, entry)
        self._history = self._history[:100]  # keep last 100
        self._save_history()
        self._refresh_history_list()

    def _refresh_history_list(self):
        self._history_list.clear()
        for entry in self._history:
            text = f"{entry['time']}  -  {entry['count']}/{entry['total']} renamed"
            self._history_list.addItem(QListWidgetItem(text))

    def _load_history(self):
        history_path = Path.home() / ".chou" / HISTORY_FILE
        if history_path.exists():
            try:
                self._history = json.loads(history_path.read_text(encoding="utf-8"))
            except Exception:
                self._history = []
        self._refresh_history_list()

    def _save_history(self):
        history_dir = Path.home() / ".chou"
        history_dir.mkdir(exist_ok=True)
        history_path = history_dir / HISTORY_FILE
        history_path.write_text(json.dumps(self._history, ensure_ascii=False, indent=2),
                                encoding="utf-8")

    # ---- Misc UI helpers ---------------------------------------------------

    def _toggle_history(self, checked: bool):
        self._history_widget.setVisible(checked)

    def _update_status(self):
        papers = self._model.papers
        total = len(papers)
        ok = sum(1 for p in papers if p.status == "success")
        err = sum(1 for p in papers if p.status == "error")
        self._status.showMessage(f"Total: {total}  |  Success: {ok}  |  Errors: {err}")

    def _set_ui_busy(self, busy: bool):
        self._btn_add_files.setEnabled(not busy)
        self._btn_add_folder.setEnabled(not busy)
        self._btn_process.setEnabled(not busy)
        self._btn_rename.setEnabled(not busy)
        self._btn_clear.setEnabled(not busy)
        self._drop_zone.setAcceptDrops(not busy)

    def _show_about(self):
        QMessageBox.about(
            self,
            f"About {__app_name__}",
            f"<h3>{__app_name__} ({__app_name_cn__}) v{__version__}</h3>"
            f"<p>Academic Paper PDF Renaming Tool</p>"
            f"<p>Automatically renames academic PDFs to citation-style filenames "
            f"by extracting title, author, and year from PDF content.</p>"
            f"<p><a href='https://github.com/cycleuser/Chou'>GitHub</a></p>"
        )

    # ---- Window state persistence ------------------------------------------

    def _restore_geometry(self):
        geo = self._settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)

    def closeEvent(self, event):
        self._settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    # ---- Drag & drop on main window (forward to drop zone) -----------------

    def _on_files_dropped(self, paths: List[Path]):
        self._start_processing(paths)
