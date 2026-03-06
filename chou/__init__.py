"""
Chou (瞅) - Academic Paper PDF Renaming Tool

A tool to automatically rename academic PDF papers to citation-style filenames
by extracting title, author, and year information from the PDF content.

Usage:
    CLI: chou --dir /path/to/papers --execute
    GUI: chou-gui
    API: from chou import rename_papers; result = rename_papers("./papers")
"""

from .__version__ import __version__, __app_name__, __app_name_cn__
from .api import ToolResult, rename_papers

__all__ = [
    "__version__",
    "__app_name__",
    "__app_name_cn__",
    "ToolResult",
    "rename_papers",
]
