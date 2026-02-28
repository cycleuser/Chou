"""
Author name parsing and extraction
"""

import re
from typing import List, Optional

from .models import Author
from ..utils.constants import AUTHOR_SPECIAL_CHARS


def clean_author_string(text: str) -> str:
    """
    Clean author string by removing all special markers, numbers, and symbols.
    
    Args:
        text: Raw author string from PDF
        
    Returns:
        Cleaned author string
    """
    # Remove special characters
    for char in AUTHOR_SPECIAL_CHARS:
        text = text.replace(char, ' ')
    
    # Remove regular digits
    text = re.sub(r'\d+', ' ', text)
    
    # Remove any remaining non-letter/space/comma/hyphen characters
    text = re.sub(r'[^\w\s,.\-]', ' ', text, flags=re.UNICODE)
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def extract_name_words(name_text: str) -> List[str]:
    """
    Extract valid name words from a single author's name string.
    
    Args:
        name_text: Single author's name string
        
    Returns:
        List of valid name words
    """
    words = name_text.split()
    name_words = []
    
    for word in words:
        # Remove trailing periods (e.g., "H." -> "H", "T.C." -> "T.C")
        word_clean = word.rstrip('.')
        # Skip if empty
        if not word_clean:
            continue
        # Skip if it's all lowercase
        if word_clean.islower():
            continue
        # Accept abbreviated initials like "TC", "T.C" (from "T.C.", "A.J.S.")
        initials_clean = word_clean.replace('.', '')
        if re.match(r'^[A-Z]{1,4}$', initials_clean) and len(initials_clean) <= 4:
            name_words.append(initials_clean)
            continue
        # Skip non-initial single chars
        if len(word_clean) < 2:
            continue
        # Check if it looks like a name (starts with capital, rest mostly letters)
        if re.match(r"^[A-Z\u00C0-\u024F][a-z\u00C0-\u024F\-']+$", word_clean):
            name_words.append(word_clean)
        # Also accept CamelCase or all caps names
        elif re.match(r"^[A-Z\u00C0-\u024F][A-Za-z\u00C0-\u024F\-']+$", word_clean):
            name_words.append(word_clean)
    
    if not name_words:
        # Fallback: try to extract any capitalized word
        for word in words:
            word_clean = word.rstrip('.')
            if len(word_clean) >= 2 and word_clean[0].isupper():
                alpha_count = sum(1 for c in word_clean if c.isalpha())
                if alpha_count >= len(word_clean) * 0.7:
                    name_words.append(word_clean)
    
    return name_words


def parse_all_authors(authors_text: str) -> List[Author]:
    """
    Parse author string and return list of Author objects.
    Handles both English and Chinese author names.
    
    Args:
        authors_text: Raw author string from PDF
        
    Returns:
        List of Author objects
    """
    cleaned = clean_author_string(authors_text)
    
    if not cleaned:
        return []
    
    # Check for Chinese names (2-4 CJK characters without spaces)
    chinese_name_match = re.findall(r'[\u4e00-\u9fff]{2,4}', cleaned)
    if chinese_name_match and not re.search(r'[A-Za-z]{2,}', cleaned):
        # Purely Chinese text - treat each CJK name as an author
        authors = []
        for name in chinese_name_match:
            authors.append(Author(
                full_name=name,
                surname=name[0]  # First character is surname in Chinese
            ))
        return authors
    
    # Split by comma or "and" to get individual authors
    author_parts = re.split(r'\s*,\s*|\s+and\s+', cleaned)
    
    authors = []
    for part in author_parts:
        part = part.strip()
        if not part:
            continue
        
        name_words = extract_name_words(part)
        if not name_words:
            continue
        
        full_name = ' '.join(name_words)
        surname = name_words[-1]  # Last word is typically surname
        
        authors.append(Author(full_name=full_name, surname=surname))
    
    return authors


def is_valid_author(author: Author) -> bool:
    """
    Check if an author object is valid.
    
    Args:
        author: Author object to validate
        
    Returns:
        True if valid, False otherwise
    """
    name = author.surname
    if not name:
        return False
    
    # Allow single CJK character surnames (Chinese names)
    if len(name) == 1 and '\u4e00' <= name <= '\u9fff':
        return True
    
    if len(name) < 2:
        return False
    
    alpha_count = sum(1 for c in name if c.isalpha())
    if alpha_count < len(name) * 0.7:
        return False
    
    if not name[0].isalpha():
        return False
    
    invalid_names = {'the', 'and', 'for', 'with', 'from', 'abstract', 'introduction'}
    if name.lower() in invalid_names:
        return False
    
    return True


def is_valid_authors_list(authors: List[Author]) -> bool:
    """
    Check if the extracted authors list is valid.
    
    Args:
        authors: List of Author objects
        
    Returns:
        True if valid, False otherwise
    """
    if not authors:
        return False
    
    return is_valid_author(authors[0])
