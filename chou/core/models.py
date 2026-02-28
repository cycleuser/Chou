"""
Data models for Chou
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from enum import Enum


class AuthorFormat(str, Enum):
    """Author name format options for citation filenames"""
    FIRST_SURNAME = "first_surname"
    FIRST_FULL = "first_full"
    ALL_SURNAMES = "all_surnames"
    ALL_FULL = "all_full"
    N_SURNAMES = "n_surnames"
    N_FULL = "n_full"
    
    @classmethod
    def get_description(cls, fmt: 'AuthorFormat') -> str:
        """Get human-readable description for format"""
        descriptions = {
            cls.FIRST_SURNAME: "First author surname only (e.g., Wang)",
            cls.FIRST_FULL: "First author full name (e.g., Weihao Wang)",
            cls.ALL_SURNAMES: "All authors surnames (e.g., Wang, Zhang, You)",
            cls.ALL_FULL: "All authors full names (e.g., Weihao Wang, Rufeng Zhang)",
            cls.N_SURNAMES: "First N authors surnames",
            cls.N_FULL: "First N authors full names",
        }
        return descriptions.get(fmt, "")


@dataclass
class Author:
    """Represents an author with full name and surname"""
    full_name: str
    surname: str
    
    def __str__(self) -> str:
        return self.full_name


@dataclass
class PaperInfo:
    """
    Represents extracted paper metadata and processing status.
    Used by both CLI and GUI for tracking paper processing.
    """
    file_path: Path
    title: Optional[str] = None
    authors: List[Author] = field(default_factory=list)
    year: Optional[int] = None
    new_filename: Optional[str] = None
    status: str = "pending"  # pending, success, error, skip
    error_message: Optional[str] = None
    
    @property
    def original_filename(self) -> str:
        """Get the original filename"""
        return self.file_path.name
    
    @property
    def is_valid(self) -> bool:
        """Check if paper has valid extracted data"""
        return bool(self.title and self.authors and self.year)
    
    @property
    def author_surnames(self) -> List[str]:
        """Get list of author surnames"""
        return [a.surname for a in self.authors]
    
    @property
    def first_author(self) -> Optional[Author]:
        """Get first author"""
        return self.authors[0] if self.authors else None
