"""
Chou - Unified Python API.

Provides ToolResult-based wrappers for programmatic usage
and agent integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, List

from .__version__ import __version__
from .core.models import AuthorFormat
from .core.processor import PaperProcessor


@dataclass
class ToolResult:
    """Standardised return type for all Chou API functions."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


def rename_papers(
    directory: str | Path = ".",
    *,
    recursive: bool = True,
    author_format: str = "first_surname",
    n_authors: int = 3,
    dry_run: bool = True,
    ocr_engine: str | None = None,
    device: str | None = None,
) -> ToolResult:
    """Process and rename academic PDF files in a directory.

    Parameters
    ----------
    directory : str or Path
        Directory containing PDF files.
    recursive : bool
        Whether to scan subdirectories.
    author_format : str
        One of: first_surname, first_full, all_surnames, all_full,
        n_surnames, n_full.
    n_authors : int
        Number of authors for n_surnames/n_full formats.
    dry_run : bool
        If True, preview changes without renaming.
    ocr_engine : str or None
        OCR engine name, or None for auto-detect.
    device : str or None
        "cpu", "gpu", or None for auto.

    Returns
    -------
    ToolResult
        With data containing list of paper dicts and summary stats.
    """
    try:
        fmt = AuthorFormat(author_format)
    except ValueError:
        return ToolResult(
            success=False,
            error=f"Invalid author_format: {author_format!r}. "
                  f"Valid: {[f.value for f in AuthorFormat]}",
        )

    directory = Path(directory)
    if not directory.is_dir():
        return ToolResult(success=False, error=f"Not a directory: {directory}")

    try:
        processor = PaperProcessor(
            author_format=fmt,
            n_authors=n_authors,
            ocr_engine=ocr_engine or None,
            device=device,
        )

        papers = processor.process_directory(directory, recursive=recursive)

        if not dry_run:
            papers = processor.apply_renames(papers, dry_run=False)

        results = []
        for p in papers:
            results.append({
                "original": p.original_filename,
                "new": p.new_filename or None,
                "title": p.title or None,
                "authors": [a.surname for a in p.authors] if p.authors else [],
                "year": p.year,
                "status": p.status,
                "error": p.error_message or None,
            })

        success_count = sum(1 for p in papers if p.status == "success")
        error_count = sum(1 for p in papers if p.status == "error")

        return ToolResult(
            success=error_count == 0,
            data=results,
            metadata={
                "total": len(papers),
                "success": success_count,
                "errors": error_count,
                "dry_run": dry_run,
                "directory": str(directory.resolve()),
                "version": __version__,
            },
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))
