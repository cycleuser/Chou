"""
Chinese text detection and validation utilities.

Handles detection of corrupted Chinese characters (mojibake/乱码),
Chinese thesis field extraction, and Chinese text quality assessment.
"""

import re
from typing import Optional, Tuple, List


CJK_RANGE = (0x4E00, 0x9FFF)
CJK_PUNCTUATION_RANGE = (0x3000, 0x303F)

MOJIBAKE_PATTERNS = [
    r'[\x00-\x08\x0b\x0c\x0e-\x1f]',
    r'Ã[\x80-\x9f]',
    r'[\xc0-\xff][\x80-\xbf]{2,3}',
    r'\ufffd',
]


def is_cjk_char(char: str) -> bool:
    """Check if a character is in the CJK range."""
    cp = ord(char)
    return CJK_RANGE[0] <= cp <= CJK_RANGE[1]


def is_cjk_punctuation(char: str) -> bool:
    """Check if a character is CJK punctuation."""
    cp = ord(char)
    return CJK_PUNCTUATION_RANGE[0] <= cp <= CJK_PUNCTUATION_RANGE[1]


def count_cjk_chars(text: str) -> int:
    """Count the number of CJK characters in text."""
    return sum(1 for c in text if is_cjk_char(c))


def has_chinese_content(text: str, min_chars: int = 5) -> bool:
    """
    Check if text contains meaningful Chinese content.
    
    Args:
        text: Text to check
        min_chars: Minimum CJK characters required
        
    Returns:
        True if text has at least min_chars CJK characters
    """
    return count_cjk_chars(text) >= min_chars


def detect_mojibake(text: str) -> Tuple[bool, float]:
    """
    Detect if text contains mojibake (乱码) or corrupted encoding.
    
    Mojibake indicators:
    - Control characters in printable text
    - Latin-1 supplement characters that shouldn't be there
    - Replacement characters ()
    - High ratio of garbage characters
    
    Args:
        text: Text to analyze
        
    Returns:
        Tuple of (is_corrupted, corruption_ratio)
    """
    if not text:
        return False, 0.0
    
    garbage_count = 0
    
    for pattern in MOJIBAKE_PATTERNS:
        garbage_count += len(re.findall(pattern, text))
    
    isolated_latin = re.findall(r'[À-ÿ](?![a-zA-ZÀ-ÿ])', text)
    garbage_count += len(isolated_latin)
    
    replacement_chars = text.count('\ufffd')
    garbage_count += replacement_chars
    
    control_chars = re.findall(r'[\x00-\x1f\x7f-\x9f]', text)
    garbage_count += len(control_chars)
    
    corruption_ratio = garbage_count / max(len(text), 1)
    
    is_corrupted = corruption_ratio > 0.05 or garbage_count > 10
    
    return is_corrupted, corruption_ratio


def is_chinese_text_valid(text: str) -> Tuple[bool, str]:
    """
    Check if Chinese text extraction is valid and not corrupted.
    
    Args:
        text: Extracted text from PDF
        
    Returns:
        Tuple of (is_valid, reason)
        - is_valid: True if text appears properly encoded
        - reason: Description of validation result
    """
    if not text or not text.strip():
        return False, "empty_text"
    
    cjk_count = count_cjk_chars(text)
    
    if cjk_count < 5:
        return True, "not_chinese_document"
    
    is_mojibake, ratio = detect_mojibake(text)
    if is_mojibake:
        return False, f"mojibake_detected_ratio_{ratio:.2f}"
    
    cjk_ratio = cjk_count / max(len(text), 1)
    
    garbage_between_cjk = 0
    prev_was_cjk = False
    for c in text:
        curr_is_cjk = is_cjk_char(c)
        if prev_was_cjk and curr_is_cjk:
            pass
        elif prev_was_cjk and not curr_is_cjk:
            if not c.isalnum() and not is_cjk_punctuation(c) and c not in ' \n\t，。、；：""''（）【】':
                if ord(c) > 127:
                    garbage_between_cjk += 1
        prev_was_cjk = curr_is_cjk
    
    if garbage_between_cjk > cjk_count * 0.3:
        return False, "interleaved_garbage_between_cjk"
    
    chinese_words = re.findall(r'[\u4e00-\u9fff]{2,10}', text)
    if cjk_count > 20 and len(chinese_words) < cjk_count * 0.3:
        return False, "cjk_chars_not_forming_words"
    
    return True, "valid_chinese_text"


def should_force_ocr_for_chinese(text: str) -> bool:
    """
    Determine if OCR should be forced for this Chinese text.
    
    OCR is recommended when:
    - Text appears to be Chinese but extraction is corrupted
    - Too few valid Chinese words despite many CJK characters
    - Mojibake detected
    
    Args:
        text: Extracted text from PDF
        
    Returns:
        True if OCR should be used instead of native extraction
    """
    if not text or len(text.strip()) < 10:
        return True
    
    is_valid, reason = is_chinese_text_valid(text)
    
    if not is_valid:
        return True
    
    if reason == "not_chinese_document":
        return False
    
    return False


CHINESE_THESIS_FIELD_PATTERNS = {
    'title': [
        r'论文题目[：:\s]*(.+?)(?:\n|$)',
        r'题\s*目[：:\s]*(.+?)(?:\n|$)',
        r'中\s*文\s*题\s*目[：:\s]*(.+?)(?:\n|$)',
        r'英文题目[：:\s]*(.+?)(?:\n|$)',
        r'学位论文题目[：:\s]*(.+?)(?:\n|$)',
        r'研\s*究\s*生\s*学\s*位\s*论\s*文[：:\s]*(.+?)(?:\n|$)',
        r'博士学位论文[：:\s]*(.+?)(?:\n|$)',
        r'硕士学位论文[：:\s]*(.+?)(?:\n|$)',
        r'论文名称[：:\s]*(.+?)(?:\n|$)',
    ],
    'author': [
        r'作者姓名[：:\s]*(.+?)(?:\n|$)',
        r'作\s*者[：:\s]*(.+?)(?:\n|$)',
        r'姓\s*名[：:\s]*(.+?)(?:\n|$)',
        r'研究生姓名[：:\s]*(.+?)(?:\n|$)',
        r'博士生姓名[：:\s]*(.+?)(?:\n|$)',
        r'硕士生姓名[：:\s]*(.+?)(?:\n|$)',
        r'申请人[：:\s]*(.+?)(?:\n|$)',
        r'学位申请人[：:\s]*(.+?)(?:\n|$)',
    ],
    'advisor': [
        r'指导教师[：:\s]*(.+?)(?:\n|$)',
        r'导师姓名[：:\s]*(.+?)(?:\n|$)',
        r'导\s*师[：:\s]*(.+?)(?:\n|$)',
        r'指导老师[：:\s]*(.+?)(?:\n|$)',
        r'导师[：:\s]*(.+?)(?:\n|$)',
    ],
    'institution': [
        r'所在院校[：:\s]*(.+?)(?:\n|$)',
        r'培养单位[：:\s]*(.+?)(?:\n|$)',
        r'学位授予单位[：:\s]*(.+?)(?:\n|$)',
        r'院\s*校[：:\s]*(.+?)(?:\n|$)',
        r'学\s*校[：:\s]*(.+?)(?:\n|$)',
        r'申请学位单位[：:\s]*(.+?)(?:\n|$)',
    ],
    'date': [
        r'答辩日期[：:\s]*(.+?)(?:\n|$)',
        r'论文完成日期[：:\s]*(.+?)(?:\n|$)',
        r'提交日期[：:\s]*(.+?)(?:\n|$)',
        r'日期[：:\s]*(.+?)(?:\n|$)',
    ],
    'major': [
        r'专业名称[：:\s]*(.+?)(?:\n|$)',
        r'专\s*业[：:\s]*(.+?)(?:\n|$)',
        r'研究方向[：:\s]*(.+?)(?:\n|$)',
        r'学科专业[：:\s]*(.+?)(?:\n|$)',
    ],
}


def extract_chinese_thesis_fields(text: str) -> dict:
    """
    Extract fields from Chinese thesis/dissertation cover page.
    
    Many Chinese universities format thesis cover pages with labeled fields
    like "论文题目: xxx", "作者姓名: xxx", etc.
    
    Args:
        text: Text from thesis cover page
        
    Returns:
        Dict with extracted fields: title, author, advisor, institution, etc.
    """
    result = {}
    
    for field_name, patterns in CHINESE_THESIS_FIELD_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip()
                value = re.sub(r'\s+', ' ', value)
                value = value.split('\n')[0].strip()
                if value and len(value) >= 2:
                    result[field_name] = value
                    break
    
    return result


def is_chinese_thesis(text: str) -> bool:
    """
    Detect if the text appears to be from a Chinese thesis/dissertation.
    
    Args:
        text: Text to analyze
        
    Returns:
        True if text contains thesis field markers
    """
    thesis_markers = [
        '论文题目', '论文名称', '学位论文', '博士学位论文', '硕士学位论文',
        '研究生学位论文', '研究生姓名', '博士生姓名', '硕士生姓名',
        '指导教师', '导师姓名', '答辩日期', '学位授予单位',
        '培养单位', '专业名称', '研究方向',
    ]
    
    for marker in thesis_markers:
        if marker in text:
            return True
    
    if re.search(r'硕\s*士\s*学\s*位\s*论\s*文', text):
        return True
    if re.search(r'博\s*士\s*学\s*位\s*论\s*文', text):
        return True
    
    return False


def extract_chinese_names(text: str) -> List[str]:
    """
    Extract Chinese names from text.
    
    Chinese names are typically 2-4 CJK characters, appearing in certain contexts.
    
    Args:
        text: Text containing potential Chinese names
        
    Returns:
        List of extracted name strings
    """
    names = []
    
    name_pattern = r'[\u4e00-\u9fff]{2,4}'
    candidates = re.findall(name_pattern, text)
    
    non_name_chars = set('的是在和有这不为上个大中从要以时到会出也你那就')
    
    for candidate in candidates:
        if len(candidate) == 2:
            first_char = candidate[0]
            if first_char in non_name_chars:
                continue
        
        if candidate in ['摘要', '目录', '引言', '结论', '致谢', '参考文献', 
                         '关键词', '附录', '前言', '概述', '综述', '绪论',
                         '研究生', '博士生', '硕士生', '本科生', '导师']:
            continue
        
        if re.match(r'^第.+章', candidate):
            continue
        
        if candidate in text and not re.search(rf'{candidate}[：:，,。、]', text):
            pass
        
        names.append(candidate)
    
    return names


def clean_chinese_title(title: str) -> str:
    """
    Clean extracted Chinese title.
    
    Removes common artifacts and formatting issues.
    
    Args:
        title: Raw extracted title
        
    Returns:
        Cleaned title
    """
    if not title:
        return title
    
    title = title.strip()
    
    title = re.sub(r'[\ufffd\x00-\x1f]', '', title)
    
    title = re.sub(r'^[：:\s]+', '', title)
    title = re.sub(r'[：:\s]+$', '', title)
    
    title = re.sub(r'\s+', ' ', title)
    
    if '基于' in title or '研究' in title or '分析' in title or '设计' in title:
        pass
    
    return title.strip()