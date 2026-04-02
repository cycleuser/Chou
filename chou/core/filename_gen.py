"""
Citation filename generation

Supports both Chinese and English filename formats:
- Chinese: 张三 等 (2023) - 中文标题.pdf
- English: Smith et al. (2023) - English Title.pdf
"""

import re
from typing import List, Optional

from .models import Author, AuthorFormat
from ..utils.constants import INVALID_FILENAME_CHARS, MAX_FILENAME_LENGTH
from ..utils.chinese_utils import count_cjk_chars


def _is_chinese_paper(title: str, authors: List[Author]) -> bool:
    """
    Determine if the paper is primarily Chinese based on title and authors.
    
    Args:
        title: Paper title
        authors: List of authors
        
    Returns:
        True if the paper appears to be Chinese
    """
    if not title and not authors:
        return False
    
    # Check title
    if title:
        title_cjk_ratio = count_cjk_chars(title) / max(len(title), 1)
        if title_cjk_ratio > 0.3:
            return True
    
    # Check authors
    if authors:
        cjk_author_count = sum(
            1 for a in authors 
            if _is_chinese_name(a.full_name)
        )
        if cjk_author_count > len(authors) * 0.5:
            return True
    
    return False


def abbreviate_title(title: str, max_length: int = 50) -> str:
    """
    Abbreviate a long title by keeping the first N characters and adding ellipsis.
    
    For academic titles, tries to preserve meaningful words by breaking at word boundaries.
    
    Args:
        title: The full title to abbreviate
        max_length: Maximum length of abbreviated title (default: 50)
        
    Returns:
        Abbreviated title with ellipsis if it was truncated
    """
    if not title or len(title) <= max_length:
        return title
    
    # Try to find a good break point (space, hyphen, colon)
    truncated = title[:max_length]
    
    # Look for last space within the limit
    last_space = truncated.rfind(' ')
    last_hyphen = truncated.rfind('-')
    last_colon = truncated.rfind(':')
    
    # Find the best break point
    break_point = max(last_space, last_hyphen, last_colon)
    
    if break_point > max_length * 0.5:  # Only break if we're past halfway
        return title[:break_point].strip() + '...'
    
    # No good break point found, just truncate
    return title[:max_length-3].strip() + '...'


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
    n: int = 3,
    use_chinese: bool = False
) -> Optional[str]:
    """
    Format author list according to specified format.
    
    For Chinese names, always uses full name since single-character
    surnames are not meaningful in filenames.
    
    Args:
        authors: List of Author objects
        format_type: Author format type
        n: Number of authors for n_surnames/n_full formats
        use_chinese: If True, use Chinese format (等 instead of et al.)
        
    Returns:
        Formatted author string for filename
    """
    if not authors:
        return None
    
    et_al = "等" if use_chinese else "et al."
    
    first_author = authors[0]
    first_is_chinese = _is_chinese_name(first_author.full_name)
    
    if format_type == AuthorFormat.FIRST_SURNAME:
        if first_is_chinese:
            return first_author.full_name
        return first_author.surname
    
    elif format_type == AuthorFormat.FIRST_FULL:
        return first_author.full_name
    
    elif format_type == AuthorFormat.ALL_SURNAMES:
        names = []
        for a in authors:
            if _is_chinese_name(a.full_name):
                names.append(a.full_name)
            else:
                names.append(a.surname)
        if len(names) > 5:
            return ', '.join(names[:5]) + f' {et_al}'
        return ', '.join(names)
    
    elif format_type == AuthorFormat.ALL_FULL:
        names = [a.full_name for a in authors]
        if len(names) > 3:
            return ', '.join(names[:3]) + f' {et_al}'
        return ', '.join(names)
    
    elif format_type == AuthorFormat.N_SURNAMES:
        names = []
        for a in authors[:n]:
            if _is_chinese_name(a.full_name):
                names.append(a.full_name)
            else:
                names.append(a.surname)
        if len(authors) > n:
            return ', '.join(names) + f' {et_al}'
        return ', '.join(names)
    
    elif format_type == AuthorFormat.N_FULL:
        names = [a.full_name for a in authors[:n]]
        if len(authors) > n:
            return ', '.join(names) + f' {et_al}'
        return ', '.join(names)
    
    return first_author.surname


def generate_citation_filename(
    title: str,
    authors: List[Author],
    year: int,
    author_format: AuthorFormat = AuthorFormat.FIRST_SURNAME,
    n: int = 3,
    abbreviate_titles: bool = False,
    max_title_length: int = 50,
    include_journal: bool = False,
    journal: Optional[str] = None,
    abbreviate_journal: bool = False,
    max_journal_length: int = 30,
) -> str:
    """
    Generate citation-style filename.
    
    Automatically detects paper language and uses appropriate format:
    - Chinese: 作者 等 (年份) - 中文标题.pdf
    - English: Author et al. (Year) - English Title.pdf
    
    Ensures the final filename does not exceed system limits (typically 255 bytes).
    
    Args:
        title: Paper title
        authors: List of Author objects
        year: Publication year
        author_format: Author format type
        n: Number of authors for n_* formats
        abbreviate_titles: Whether to abbreviate long titles
        max_title_length: Maximum length for title before abbreviation
        include_journal: Whether to include journal name in filename
        journal: Journal/conference name
        abbreviate_journal: Whether to abbreviate long journal names
        max_journal_length: Maximum length for journal name before abbreviation
        
    Returns:
        Generated filename
    """
    is_chinese = _is_chinese_paper(title, authors)
    
    title_clean = sanitize_filename(title)
    if abbreviate_titles:
        title_clean = abbreviate_title(title_clean, max_title_length)
    
    author_str = format_authors_for_filename(
        authors, 
        author_format, 
        n,
        use_chinese=is_chinese
    )
    if not author_str:
        author_str = "Unknown" if not is_chinese else "未知"
    author_clean = sanitize_filename(author_str)
    
    parts = [author_clean, f"({year})"]
    
    if include_journal and journal:
        journal_clean = sanitize_filename(journal)
        if abbreviate_journal and len(journal_clean) > max_journal_length:
            journal_clean = abbreviate_title(journal_clean, max_journal_length)
        parts.append(f"- {journal_clean}")
    
    parts.append(f"- {title_clean}")
    
    add_et_al = author_format in [AuthorFormat.FIRST_SURNAME, AuthorFormat.FIRST_FULL] and len(authors) > 1
    
    if add_et_al:
        et_al = "等" if is_chinese else "et al."
        filename = f"{parts[0]} {et_al} {' '.join(parts[1:])}.pdf"
    else:
        filename = f"{' '.join(parts)}.pdf"
    
    max_total_length = MAX_FILENAME_LENGTH
    if len(filename) > max_total_length:
        if add_et_al:
            et_al = "等" if is_chinese else "et al."
            prefix = f"{parts[0]} {et_al} {parts[1]}"
        else:
            prefix = f"{parts[0]} {parts[1]}"
        
        suffix = ".pdf"
        available = max_total_length - len(prefix) - len(suffix) - 3
        
        if available > 10:
            truncated_title = title_clean[:available]
            last_space = truncated_title.rfind(' ')
            if last_space > available * 0.5:
                truncated_title = truncated_title[:last_space]
            filename = f"{prefix} - {truncated_title.strip()}{suffix}"
        else:
            filename = filename[:max_total_length-4] + ".pdf"
    
    return filename
