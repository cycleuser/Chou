"""
Year extraction from PDF text - supports English and Chinese
"""

import re
from typing import Optional, List, Tuple

from ..utils.constants import CONFERENCE_NAMES, ORDINAL_MAP, CHINESE_DIGIT_MAP


def chinese_year_to_int(chinese_year: str) -> Optional[int]:
    """
    Convert Chinese year like '二〇二三' or '二零二三' to integer 2023.
    
    Args:
        chinese_year: Chinese numeral year string
        
    Returns:
        Integer year or None if conversion fails
    """
    digits = []
    for char in chinese_year:
        if char in CHINESE_DIGIT_MAP:
            val = CHINESE_DIGIT_MAP[char]
            if val <= 9:
                digits.append(val)
    
    if len(digits) == 4:
        return digits[0] * 1000 + digits[1] * 100 + digits[2] * 10 + digits[3]
    return None


def edition_to_year(edition: int, conference: str = 'AAAI') -> int:
    """
    Convert conference edition number to year.
    
    Args:
        edition: Conference edition number
        conference: Conference name (default: AAAI)
        
    Returns:
        Estimated year
    """
    # AAAI-37 = 2023, so base is 2023 - 37 = 1986
    if conference.upper() == 'AAAI':
        return 1986 + edition
    # Default: assume recent conference, edition roughly matches last 2 digits of year
    if edition < 50:
        return 2000 + edition
    return 1900 + edition


def extract_year_from_text(text: str) -> Optional[int]:
    """
    Extract publication year from PDF text using comprehensive strategies.
    Designed to work with any academic paper in English or Chinese.
    
    Strategies (in priority order):
    1. Conference abbreviation with year (e.g., "CVPR 2023", "NeurIPS'22")
    2. Ordinal conference edition (e.g., "Thirty-Seventh AAAI")
    3. Copyright notice (English and Chinese)
    4. Published/Accepted date patterns (English and Chinese)
    5. Chinese year patterns (e.g., "2023年", "二〇二三年")
    6. Journal volume/issue with year
    7. arXiv identifier (e.g., "arXiv:2301.12345")
    8. DOI with year
    9. Date patterns (month year, year month) in English and Chinese
    10. Most frequent plausible year in document
    
    Args:
        text: Text content from PDF
        
    Returns:
        Extracted year or None if not found
    """
    if not text:
        return None
    
    year_candidates: List[Tuple[int, int]] = []  # (year, confidence)
    
    # Strategy 1: Conference abbreviation with year
    for conf in CONFERENCE_NAMES:
        patterns = [
            rf"\b{conf}[-\s'']?(\d{{2}})\b",  # CVPR'23, AAAI-23
            rf"\b{conf}[-\s]?(20\d{{2}})\b",   # CVPR 2023, AAAI 2023
            rf"(20\d{{2}})\s*{conf}\b",         # 2023 CVPR
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                year_str = match.group(1)
                if len(year_str) == 2:
                    year = 2000 + int(year_str)
                else:
                    year = int(year_str)
                if 1990 <= year <= 2030:
                    year_candidates.append((year, 100))
    
    # Strategy 2: Ordinal conference edition
    text_lower = text.lower()
    for ordinal, edition in ORDINAL_MAP.items():
        for conf in CONFERENCE_NAMES:
            pattern = rf'\b{ordinal}\s+{conf.lower()}\b'
            if re.search(pattern, text_lower):
                year = edition_to_year(edition, conf)
                if 1990 <= year <= 2030:
                    year_candidates.append((year, 90))
    
    # Strategy 3: Copyright notice (English)
    copyright_patterns = [
        r'[Cc]opyright\s*[©®]?\s*((?:19|20)\d{2})',
        r'©\s*((?:19|20)\d{2})',
        r'\(c\)\s*((?:19|20)\d{2})',
        r'[Cc]opyright\s+(?:by\s+)?(?:\w+\s+)*((?:19|20)\d{2})',
    ]
    for pattern in copyright_patterns:
        match = re.search(pattern, text)
        if match:
            year = int(match.group(1))
            if 1990 <= year <= 2030:
                year_candidates.append((year, 85))
    
    # Strategy 3b: Copyright notice (Chinese)
    chinese_copyright_patterns = [
        r'版权所有[©®]?\s*((?:19|20)\d{2})',
        r'版权[©®]?\s*((?:19|20)\d{2})',
        r'((?:19|20)\d{2})\s*版权',
    ]
    for pattern in chinese_copyright_patterns:
        match = re.search(pattern, text)
        if match:
            year = int(match.group(1))
            if 1990 <= year <= 2030:
                year_candidates.append((year, 85))
    
    # Strategy 4: Published/Accepted/Received date patterns (English)
    pub_patterns = [
        r'[Pp]ublished:?\s*\w*\s*((?:19|20)\d{2})',
        r'[Aa]ccepted:?\s*\w*\s*((?:19|20)\d{2})',
        r'[Rr]eceived:?\s*\w*\s*((?:19|20)\d{2})',
        r'[Oo]nline:?\s*\w*\s*((?:19|20)\d{2})',
        r'[Pp]ublication\s+[Dd]ate:?\s*\w*\s*((?:19|20)\d{2})',
        r'[Aa]vailable\s+[Oo]nline:?\s*\w*\s*((?:19|20)\d{2})',
    ]
    for pattern in pub_patterns:
        match = re.search(pattern, text)
        if match:
            year = int(match.group(1))
            if 1990 <= year <= 2030:
                year_candidates.append((year, 80))
    
    # Strategy 4b: Published/Accepted/Received date patterns (Chinese)
    chinese_pub_patterns = [
        r'发表[于日期:：]*\s*((?:19|20)\d{2})',
        r'出版[日期:：]*\s*((?:19|20)\d{2})',
        r'接收[日期:：]*\s*((?:19|20)\d{2})',
        r'录用[日期:：]*\s*((?:19|20)\d{2})',
        r'收稿[日期:：]*\s*((?:19|20)\d{2})',
        r'修回[日期:：]*\s*((?:19|20)\d{2})',
        r'刊出[日期:：]*\s*((?:19|20)\d{2})',
        r'网络出版[日期:：]*\s*((?:19|20)\d{2})',
        r'发布[日期:：]*\s*((?:19|20)\d{2})',
    ]
    for pattern in chinese_pub_patterns:
        match = re.search(pattern, text)
        if match:
            year = int(match.group(1))
            if 1990 <= year <= 2030:
                year_candidates.append((year, 80))
    
    # Strategy 5: Chinese year patterns
    chinese_year_arabic = re.findall(r'((?:19|20)\d{2})\s*年', text)
    for year_str in chinese_year_arabic:
        year = int(year_str)
        if 1990 <= year <= 2030:
            year_candidates.append((year, 78))
    
    # Chinese numeral years: 二〇二三年, 二零二三年
    chinese_numeral_pattern = r'([一二三四五六七八九零〇]{4})\s*年'
    chinese_numeral_matches = re.findall(chinese_numeral_pattern, text)
    for cn_year in chinese_numeral_matches:
        year = chinese_year_to_int(cn_year)
        if year and 1990 <= year <= 2030:
            year_candidates.append((year, 78))
    
    # Strategy 6: Journal volume with year
    journal_patterns = [
        r'[Vv]ol(?:ume)?\.?\s*\d+.*?((?:19|20)\d{2})',
        r'\(\s*((?:19|20)\d{2})\s*\)',
        r',\s*((?:19|20)\d{2})\s*$',
        r'第\s*\d+\s*卷.*?((?:19|20)\d{2})',
        r'第\s*\d+\s*期.*?((?:19|20)\d{2})',
    ]
    for pattern in journal_patterns:
        matches = re.findall(pattern, text)
        for year_str in matches:
            year = int(year_str)
            if 1990 <= year <= 2030:
                year_candidates.append((year, 70))
    
    # Strategy 7: arXiv identifier
    arxiv_match = re.search(r'arXiv[:\s]+(\d{2})(\d{2})\.\d+', text, re.IGNORECASE)
    if arxiv_match:
        year = 2000 + int(arxiv_match.group(1))
        if 2000 <= year <= 2030:
            year_candidates.append((year, 75))
    
    # Strategy 8: DOI with year
    doi_match = re.search(r'10\.\d+/\w+\.((?:19|20)\d{2})\.', text)
    if doi_match:
        year = int(doi_match.group(1))
        if 1990 <= year <= 2030:
            year_candidates.append((year, 75))
    
    # Strategy 9: Date patterns with month (English)
    months_en = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    date_patterns_en = [
        rf'{months_en}\.?\s+((?:19|20)\d{{2}})',
        rf'((?:19|20)\d{{2}})\s*{months_en}',
        rf'\d{{1,2}}\s+{months_en}\s+((?:19|20)\d{{2}})',
        rf'{months_en}\s+\d{{1,2}},?\s+((?:19|20)\d{{2}})',
    ]
    for pattern in date_patterns_en:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for year_str in matches:
            year = int(year_str)
            if 1990 <= year <= 2030:
                year_candidates.append((year, 60))
    
    # Strategy 9b: Date patterns with month (Chinese)
    chinese_date_patterns = [
        r'((?:19|20)\d{2})\s*年\s*\d{1,2}\s*月',
        r'((?:19|20)\d{2})[年\-/]\d{1,2}[月\-/]',
    ]
    for pattern in chinese_date_patterns:
        matches = re.findall(pattern, text)
        for year_str in matches:
            year = int(year_str)
            if 1990 <= year <= 2030:
                year_candidates.append((year, 65))
    
    # Strategy 10: Find all 4-digit years and pick most plausible
    all_years = re.findall(r'\b((?:19|20)\d{2})\b', text)
    year_counts = {}
    for y in all_years:
        year = int(y)
        if 1990 <= year <= 2030:
            year_counts[year] = year_counts.get(year, 0) + 1
    
    for year, count in year_counts.items():
        confidence = min(50, 20 + count * 5)
        year_candidates.append((year, confidence))
    
    # Select the best year candidate
    if not year_candidates:
        return None
    
    year_candidates.sort(key=lambda x: (x[1], x[0]), reverse=True)
    return year_candidates[0][0]
