"""
Chou - OpenAI function-calling tool definitions.

Provides TOOLS list and dispatch() for LLM agent integration.
"""

from __future__ import annotations

import json
from typing import Any

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "chou_rename_papers",
            "description": (
                "Scan a directory for academic PDF files and rename them to "
                "citation-style filenames (Author_Year_Title.pdf) by extracting "
                "metadata from the PDF content. Supports OCR for scanned documents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Path to the directory containing PDF files.",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Scan subdirectories recursively.",
                        "default": True,
                    },
                    "author_format": {
                        "type": "string",
                        "enum": [
                            "first_surname",
                            "first_full",
                            "all_surnames",
                            "all_full",
                            "n_surnames",
                            "n_full",
                        ],
                        "description": "Author name format for the filename.",
                        "default": "first_surname",
                    },
                    "n_authors": {
                        "type": "integer",
                        "description": "Number of authors for n_surnames/n_full formats.",
                        "default": 3,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview changes without actually renaming.",
                        "default": True,
                    },
                    "ocr_engine": {
                        "type": "string",
                        "description": "OCR engine name, or null for auto-detect.",
                    },
                    "device": {
                        "type": "string",
                        "enum": ["cpu", "gpu"],
                        "description": "Device for OCR inference.",
                    },
                },
                "required": ["directory"],
            },
        },
    },
]


def dispatch(name: str, arguments: dict[str, Any] | str) -> dict:
    """Dispatch a tool call to the appropriate API function.

    Parameters
    ----------
    name : str
        Function name from the tool call.
    arguments : dict or str
        Arguments dict or JSON string.

    Returns
    -------
    dict
        ToolResult as a dictionary.
    """
    if isinstance(arguments, str):
        arguments = json.loads(arguments)

    if name == "chou_rename_papers":
        from .api import rename_papers

        result = rename_papers(**arguments)
        return result.to_dict()

    raise ValueError(f"Unknown tool: {name}")
