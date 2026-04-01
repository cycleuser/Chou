"""Chou Utilities"""

from .constants import CONFERENCE_NAMES, ORDINAL_MAP, CHINESE_DIGIT_MAP
from .chinese_utils import (
    is_cjk_char,
    count_cjk_chars,
    has_chinese_content,
    detect_mojibake,
    is_chinese_text_valid,
    should_force_ocr_for_chinese,
    extract_chinese_thesis_fields,
    is_chinese_thesis,
    extract_chinese_names,
    clean_chinese_title,
)

__all__ = [
    "CONFERENCE_NAMES",
    "ORDINAL_MAP",
    "CHINESE_DIGIT_MAP",
    "is_cjk_char",
    "count_cjk_chars",
    "has_chinese_content",
    "detect_mojibake",
    "is_chinese_text_valid",
    "should_force_ocr_for_chinese",
    "extract_chinese_thesis_fields",
    "is_chinese_thesis",
    "extract_chinese_names",
    "clean_chinese_title",
]
