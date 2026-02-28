"""
Citation filename generation
"""

import re
from typing import List, Optional

from .models import Author, AuthorFormat
from ..utils.constants import INVALID_FILENAME_CHARS, MAX_FILENAME_LENGTH


def _is_chinese_name(name: str) -> bool:
    """
    Check if a name is primarily Chinese (CJK characters).
    
    Args:
        name: Name string to check
        
    Returns:
        True if the name is primarily Chinese
    """
    if not name:
        return False
    cjk_count = sum(1 for c in name if '\u4e00' <= c <= '\u9fff')
    return cjk_count >= len(name) * 0.5 and cjk_count >= 2


def sanitize_filename(name: str) -> str:
    """
    Remove or replace characters not allowed in filenames.
    
    Args:
        name: Raw filename string
        
    Returns:
        Sanitized filename
    """
    for char in INVALID_FILENAME_CHARS:
        name = name.replace(char, '')
    
    name = re.sub(r'\s+', ' ', name)
    
    if len(name) > MAX_FILENAME_LENGTH:
        name = name[:MAX_FILENAME_LENGTH]
    
    return name.strip()


def format_authors_for_filename(
    authors: List[Author],
    format_type: AuthorFormat,
    n: int = 3
) -> Optional[str]:
    """
    Format author list according to specified format.
    
    For Chinese names, always uses full name since single-character
    surnames are not meaningful in filenames.
    
    Args:
        authors: List of Author objects
        format_type: Author format type
        n: Number of authors for n_surnames/n_full formats
        
    Returns:
        Formatted author string for filename
    """
    if not authors:
        return None
    
    # Check if first author has Chinese name
    first_author = authors[0]
    first_is_chinese = _is_chinese_name(first_author.full_name)
    
    if format_type == AuthorFormat.FIRST_SURNAME:
        # Use full name for Chinese authors
        if first_is_chinese:
            return first_author.full_name
        return first_author.surname
    
    elif format_type == AuthorFormat.FIRST_FULL:
        return first_author.full_name
    
    elif format_type == AuthorFormat.ALL_SURNAMES:
        # For Chinese names, use full names
        names = []
        for a in authors:
            if _is_chinese_name(a.full_name):
                names.append(a.full_name)
            else:
                names.append(a.surname)
        if len(names) > 5:
            return ', '.join(names[:5]) + ' et al.'
        return ', '.join(names)
    
    elif format_type == AuthorFormat.ALL_FULL:
        names = [a.full_name for a in authors]
        if len(names) > 3:
            return ', '.join(names[:3]) + ' et al.'
        return ', '.join(names)
    
    elif format_type == AuthorFormat.N_SURNAMES:
        # For Chinese names, use full names
        names = []
        for a in authors[:n]:
            if _is_chinese_name(a.full_name):
                names.append(a.full_name)
            else:
                names.append(a.surname)
        if len(authors) > n:
            return ', '.join(names) + ' et al.'
        return ', '.join(names)
    
    elif format_type == AuthorFormat.N_FULL:
        names = [a.full_name for a in authors[:n]]
        if len(authors) > n:
            return ', '.join(names) + ' et al.'
        return ', '.join(names)
    
    return first_author.surname


def generate_citation_filename(
    title: str,
    authors: List[Author],
    year: int,
    author_format: AuthorFormat = AuthorFormat.FIRST_SURNAME,
    n: int = 3
) -> str:
    """
    Generate citation-style filename.
    
    Format: 'Author(s) (Year) - Title.pdf'
    
    Args:
        title: Paper title
        authors: List of Author objects
        year: Publication year
        author_format: Author format type
        n: Number of authors for n_* formats
        
    Returns:
        Generated filename
    """
    title_clean = sanitize_filename(title)
    
    author_str = format_authors_for_filename(authors, author_format, n)
    if not author_str:
        author_str = "Unknown"
    author_clean = sanitize_filename(author_str)
    
    # Add "et al." only for single-author formats when there are multiple authors
    if author_format in [AuthorFormat.FIRST_SURNAME, AuthorFormat.FIRST_FULL] and len(authors) > 1:
        return f"{author_clean} et al. ({year}) - {title_clean}.pdf"
    else:
        return f"{author_clean} ({year}) - {title_clean}.pdf"
