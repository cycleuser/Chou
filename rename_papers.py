#!/usr/bin/env python3
"""
AAAI Paper Renamer - Extracts title and author information from PDF first pages
and renames files to citation format: "FirstAuthor et al. (Year) - Title.pdf"
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rename_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    logger.error("PyMuPDF not installed. Run: pip install PyMuPDF")
    sys.exit(1)

# ---------------------------------------------------------------------------
# OCR support (all backends optional)
# ---------------------------------------------------------------------------
import io
from abc import ABC, abstractmethod

OCR_MIN_TEXT_LENGTH = 50
OCR_DEFAULT_DPI = 250
OCR_DEFAULT_MAX_PAGES = 3
_ENGINE_PRIORITY = ["surya", "paddleocr", "rapidocr", "easyocr", "tesseract"]
_ocr_engine_cache = {}


class _OcrEngine(ABC):
    name: str = "base"
    @abstractmethod
    def ocr_image(self, image_bytes: bytes) -> str: ...
    @staticmethod
    @abstractmethod
    def is_available() -> bool: ...


class _SuryaOcrEngine(_OcrEngine):
    name = "surya"
    def __init__(self):
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
        logger.info("Initializing Surya OCR engine (may download models on first run)...")
        foundation = FoundationPredictor()
        self._recognition = RecognitionPredictor(foundation)
        self._detection = DetectionPredictor()
    @staticmethod
    def is_available() -> bool:
        try:
            from surya.foundation import FoundationPredictor  # noqa
            from surya.recognition import RecognitionPredictor  # noqa
            from surya.detection import DetectionPredictor  # noqa
            return True
        except ImportError: return False
    def ocr_image(self, image_bytes: bytes) -> str:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        predictions = self._recognition([img], det_predictor=self._detection)
        lines = []
        for page_pred in predictions:
            for text_line in page_pred.text_lines:
                if text_line.text and text_line.text.strip():
                    lines.append(text_line.text.strip())
        return "\n".join(lines)


class _PaddleOcrEngine(_OcrEngine):
    name = "paddleocr"
    def __init__(self):
        from paddleocr import PaddleOCR
        logger.info("Initializing PaddleOCR engine...")
        self._r = PaddleOCR(use_textline_orientation=True, lang="ch")
    @staticmethod
    def is_available() -> bool:
        try: from paddleocr import PaddleOCR; return True  # noqa
        except ImportError: return False
    def ocr_image(self, image_bytes: bytes) -> str:
        import numpy as np; from PIL import Image
        img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        results = self._r.predict(img)
        lines = []
        for res in results:
            if hasattr(res, 'rec_texts') and res.rec_texts:
                lines.extend(res.rec_texts)
        return "\n".join(lines)


class _RapidOcrEngine(_OcrEngine):
    name = "rapidocr"
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        logger.info("Initializing RapidOCR engine...")
        self._r = RapidOCR()
    @staticmethod
    def is_available() -> bool:
        try: from rapidocr_onnxruntime import RapidOCR; return True  # noqa
        except ImportError: return False
    def ocr_image(self, image_bytes: bytes) -> str:
        import numpy as np; from PIL import Image
        img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        res, _ = self._r(img)
        return "\n".join(str(it[1]) for it in res if it and len(it) >= 2) if res else ""


class _EasyOcrEngine(_OcrEngine):
    name = "easyocr"
    def __init__(self):
        import easyocr
        logger.info("Initializing EasyOCR engine (may download models on first run)...")
        self._r = easyocr.Reader(["en", "ch_sim"], verbose=False)
    @staticmethod
    def is_available() -> bool:
        try: import easyocr; return True  # noqa
        except ImportError: return False
    def ocr_image(self, image_bytes: bytes) -> str:
        res = self._r.readtext(image_bytes, detail=0)
        return "\n".join(res) if res else ""


class _TesseractOcrEngine(_OcrEngine):
    name = "tesseract"
    def __init__(self):
        import pytesseract
        logger.info("Initializing Tesseract OCR engine...")
        pytesseract.get_tesseract_version()
        self._pt = pytesseract
    @staticmethod
    def is_available() -> bool:
        try: import pytesseract; pytesseract.get_tesseract_version(); return True  # noqa
        except Exception: return False
    def ocr_image(self, image_bytes: bytes) -> str:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return self._pt.image_to_string(img, lang="eng+chi_sim") or ""


_OCR_ENGINE_CLASSES = {
    "surya": _SuryaOcrEngine, "paddleocr": _PaddleOcrEngine, "rapidocr": _RapidOcrEngine,
    "easyocr": _EasyOcrEngine, "tesseract": _TesseractOcrEngine,
}


def _get_ocr_engine(engine_name=None):
    """Get or create an OCR engine (cached singleton)."""
    names = [engine_name] if engine_name else _ENGINE_PRIORITY
    for n in names:
        if n in _ocr_engine_cache:
            return _ocr_engine_cache[n]
        cls = _OCR_ENGINE_CLASSES.get(n)
        if cls and cls.is_available():
            try:
                inst = cls()
                _ocr_engine_cache[n] = inst
                return inst
            except Exception as e:
                logger.warning(f"Failed to init OCR engine {n}: {e}")
    return None


def _extract_text_with_ocr(pdf_path, max_pages=OCR_DEFAULT_MAX_PAGES, dpi=OCR_DEFAULT_DPI, engine_name=None):
    """OCR fallback: render pages to images then OCR."""
    engine = _get_ocr_engine(engine_name)
    if engine is None:
        return ""
    logger.info(f"OCR: processing {pdf_path} with {engine.name} (up to {max_pages} pages)")
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.error(f"Cannot open PDF {pdf_path}: {e}")
        return ""
    all_text = []
    pages_to_read = min(len(doc), max_pages)
    for i in range(pages_to_read):
        try:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = doc[i].get_pixmap(matrix=mat)
            text = engine.ocr_image(pix.tobytes("png"))
            if text and text.strip():
                all_text.append(text.strip())
        except Exception as e:
            logger.warning(f"  OCR failed on page {i+1}: {e}")
    doc.close()
    combined = "\n".join(all_text)
    logger.info(f"OCR: extracted {len(combined)} chars from {pages_to_read} pages")
    return combined


# Conference year mapping (fallback only)
AAAI_YEAR_MAP = {
    'AAAI_37': 2023,  # AAAI-23
    'AAAI_38': 2024,  # AAAI-24
    'AAAI_39': 2025,  # AAAI-25
}

# Ordinal number to integer mapping for conference editions
ORDINAL_MAP = {
    'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
    'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
    'eleventh': 11, 'twelfth': 12, 'thirteenth': 13, 'fourteenth': 14, 'fifteenth': 15,
    'sixteenth': 16, 'seventeenth': 17, 'eighteenth': 18, 'nineteenth': 19, 'twentieth': 20,
    'twenty-first': 21, 'twenty-second': 22, 'twenty-third': 23, 'twenty-fourth': 24, 'twenty-fifth': 25,
    'twenty-sixth': 26, 'twenty-seventh': 27, 'twenty-eighth': 28, 'twenty-ninth': 29, 'thirtieth': 30,
    'thirty-first': 31, 'thirty-second': 32, 'thirty-third': 33, 'thirty-fourth': 34, 'thirty-fifth': 35,
    'thirty-sixth': 36, 'thirty-seventh': 37, 'thirty-eighth': 38, 'thirty-ninth': 39, 'fortieth': 40,
    'forty-first': 41, 'forty-second': 42, 'forty-third': 43, 'forty-fourth': 44, 'forty-fifth': 45,
}

# Common academic conference/venue abbreviations
CONFERENCE_NAMES = [
    'AAAI', 'IJCAI', 'NeurIPS', 'NIPS', 'ICML', 'ICLR', 'CVPR', 'ICCV', 'ECCV',
    'ACL', 'EMNLP', 'NAACL', 'COLING', 'SIGIR', 'WWW', 'KDD', 'ICDE', 'VLDB',
    'SIGMOD', 'PODS', 'CIKM', 'WSDM', 'RecSys', 'UAI', 'AISTATS', 'COLT',
    'ICRA', 'IROS', 'RSS', 'CoRL', 'MICCAI', 'ISBI', 'IPMI',
    'CHI', 'UIST', 'IUI', 'CSCW', 'UbiComp', 'MobiCom', 'MobiSys',
    'OSDI', 'SOSP', 'NSDI', 'EuroSys', 'ASPLOS', 'ISCA', 'MICRO', 'HPCA',
    'CCS', 'Oakland', 'USENIX', 'NDSS', 'CRYPTO', 'EUROCRYPT',
    'SIGGRAPH', 'EuroGraphics', 'ACM MM', 'ICME', 'ICASSP',
    'INTERSPEECH', 'ICPR', 'BMVC', 'WACV', 'ACCV', 'ACMMM',
]

# Chinese numeral to digit mapping
CHINESE_DIGIT_MAP = {
    '零': 0, '〇': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5,
    '陆': 6, '柒': 7, '捌': 8, '玖': 9, '拾': 10,
}


def chinese_year_to_int(chinese_year: str) -> Optional[int]:
    """Convert Chinese year like '二〇二三' or '二零二三' to integer 2023."""
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
    """Convert conference edition number to year."""
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
    """
    if not text:
        return None
    
    year_candidates = []  # Collect (year, confidence) tuples
    
    # Strategy 1: Conference abbreviation with year
    # e.g., "CVPR 2023", "NeurIPS 2022", "AAAI-23", "ICML'21"
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
                    year_candidates.append((year, 100))  # High confidence
    
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
    # Pattern: "2023年" or "二〇二三年" / "二零二三年"
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
    # e.g., "Vol. 35, No. 4, 2023" or "Volume 12 (2022)"
    journal_patterns = [
        r'[Vv]ol(?:ume)?\.?\s*\d+.*?((?:19|20)\d{2})',
        r'\(\s*((?:19|20)\d{2})\s*\)',  # (2023)
        r',\s*((?:19|20)\d{2})\s*$',     # ends with year
        r'第\s*\d+\s*卷.*?((?:19|20)\d{2})',  # Chinese: 第35卷, 2023
        r'第\s*\d+\s*期.*?((?:19|20)\d{2})',  # Chinese: 第4期, 2023
    ]
    for pattern in journal_patterns:
        matches = re.findall(pattern, text)
        for year_str in matches:
            year = int(year_str)
            if 1990 <= year <= 2030:
                year_candidates.append((year, 70))
    
    # Strategy 7: arXiv identifier
    # e.g., "arXiv:2301.12345" -> 2023, "arXiv:1912.00001" -> 2019
    arxiv_match = re.search(r'arXiv[:\s]+(\d{2})(\d{2})\.\d+', text, re.IGNORECASE)
    if arxiv_match:
        year = 2000 + int(arxiv_match.group(1))
        if 2000 <= year <= 2030:
            year_candidates.append((year, 75))
    
    # Strategy 8: DOI with year
    # Some DOIs contain year: 10.1109/CVPR.2023.12345
    doi_match = re.search(r'10\.\d+/\w+\.((?:19|20)\d{2})\.', text)
    if doi_match:
        year = int(doi_match.group(1))
        if 1990 <= year <= 2030:
            year_candidates.append((year, 75))
    
    # Strategy 9: Date patterns with month (English)
    months_en = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    date_patterns_en = [
        rf'{months_en}\.?\s+((?:19|20)\d{{2}})',  # March 2023
        rf'((?:19|20)\d{{2}})\s*{months_en}',      # 2023 March
        rf'\d{{1,2}}\s+{months_en}\s+((?:19|20)\d{{2}})',  # 15 March 2023
        rf'{months_en}\s+\d{{1,2}},?\s+((?:19|20)\d{{2}})',  # March 15, 2023
    ]
    for pattern in date_patterns_en:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for year_str in matches:
            year = int(year_str)
            if 1990 <= year <= 2030:
                year_candidates.append((year, 60))
    
    # Strategy 9b: Date patterns with month (Chinese)
    # e.g., "2023年3月", "2023年03月15日"
    chinese_date_patterns = [
        r'((?:19|20)\d{2})\s*年\s*\d{1,2}\s*月',  # 2023年3月
        r'((?:19|20)\d{2})[年\-/]\d{1,2}[月\-/]',  # 2023年3月 or 2023-03
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
    
    # Add frequent years with lower confidence
    for year, count in year_counts.items():
        # More occurrences = higher confidence, but capped
        confidence = min(50, 20 + count * 5)
        year_candidates.append((year, confidence))
    
    # Select the best year candidate
    if not year_candidates:
        return None
    
    # Sort by confidence (descending), then by year (descending, prefer recent)
    year_candidates.sort(key=lambda x: (x[1], x[0]), reverse=True)
    
    return year_candidates[0][0]


def sanitize_filename(name: str) -> str:
    """Remove or replace characters not allowed in filenames."""
    # Replace problematic characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    # Remove multiple spaces
    name = re.sub(r'\s+', ' ', name)
    # Limit length (Windows max is 255, leave room for path)
    if len(name) > 200:
        name = name[:200]
    return name.strip()


def clean_author_string(text: str) -> str:
    """Clean author string by removing all special markers, numbers, and symbols."""
    # Remove various Unicode asterisk variants and footnote markers
    special_chars = [
        '*', '∗', '⁎', '✱', '＊',  # asterisks
        '†', '‡', '§', '¶', '∥',   # footnote markers
        '¹', '²', '³', '⁴', '⁵', '⁶', '⁷', '⁸', '⁹', '⁰',  # superscript numbers
        '₁', '₂', '₃', '₄', '₅', '₆', '₇', '₈', '₉', '₀',  # subscript numbers
        '①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨',  # circled numbers
        '♠', '♣', '♦', '♥', '★', '☆',  # other markers
    ]
    for char in special_chars:
        text = text.replace(char, ' ')
    
    # Remove regular digits
    text = re.sub(r'\d+', ' ', text)
    
    # Remove any remaining non-letter/space/comma/hyphen characters that look like markers
    # Keep letters (including accented), spaces, commas, hyphens, periods
    text = re.sub(r'[^\w\s,.\-]', ' ', text, flags=re.UNICODE)
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def extract_name_words(name_text: str) -> list:
    """Extract valid name words from a single author's name string."""
    words = name_text.split()
    name_words = []
    
    for word in words:
        # Remove trailing periods (e.g., "H." -> "H")
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
                # Verify it's mostly alphabetic
                alpha_count = sum(1 for c in word_clean if c.isalpha())
                if alpha_count >= len(word_clean) * 0.7:
                    name_words.append(word_clean)
    
    return name_words


def parse_all_authors(authors_text: str) -> list:
    """
    Parse author string and return list of author dicts.
    Each dict contains: {'full_name': str, 'surname': str}
    Handles both English and Chinese author names.
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
            authors.append({
                'full_name': name,
                'surname': name[0]  # First character is surname in Chinese
            })
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
        
        authors.append({
            'full_name': full_name,
            'surname': surname
        })
    
    return authors


# Author format options
AUTHOR_FORMAT_OPTIONS = {
    'first_surname': 'First author surname only (e.g., Wang)',
    'first_full': 'First author full name (e.g., Weihao Wang)',
    'all_surnames': 'All authors surnames (e.g., Wang, Zhang, You)',
    'all_full': 'All authors full names (e.g., Weihao Wang, Rufeng Zhang)',
    'n_surnames': 'First N authors surnames',
    'n_full': 'First N authors full names',
}


def _is_chinese_name(name: str) -> bool:
    """Check if a name is primarily Chinese (CJK characters)."""
    if not name:
        return False
    cjk_count = sum(1 for c in name if '\u4e00' <= c <= '\u9fff')
    return cjk_count >= len(name) * 0.5 and cjk_count >= 2


def format_authors_for_filename(authors: list, format_type: str, n: int = 3) -> Optional[str]:
    """
    Format author list according to specified format.
    
    Args:
        authors: List of author dicts with 'full_name' and 'surname'
        format_type: One of AUTHOR_FORMAT_OPTIONS keys
        n: Number of authors for 'n_surnames' or 'n_full' formats
    
    Returns:
        Formatted author string for filename
    
    Note: For Chinese names, always uses full name since single-character
          surnames are not meaningful in filenames.
    """
    if not authors:
        return None
    
    # For Chinese names, always use full name (single char surname is not useful)
    first_author = authors[0]
    first_is_chinese = _is_chinese_name(first_author['full_name'])
    
    if format_type == 'first_surname':
        # Use full name for Chinese authors
        if first_is_chinese:
            return first_author['full_name']
        return first_author['surname']
    
    elif format_type == 'first_full':
        return first_author['full_name']
    
    elif format_type == 'all_surnames':
        # For Chinese names, use full names
        names = []
        for a in authors:
            if _is_chinese_name(a['full_name']):
                names.append(a['full_name'])
            else:
                names.append(a['surname'])
        if len(names) > 5:
            return ', '.join(names[:5]) + ' et al.'
        return ', '.join(names)
    
    elif format_type == 'all_full':
        names = [a['full_name'] for a in authors]
        if len(names) > 3:
            # Too many authors, truncate for filename length
            return ', '.join(names[:3]) + ' et al.'
        return ', '.join(names)
    
    elif format_type == 'n_surnames':
        # For Chinese names, use full names
        names = []
        for a in authors[:n]:
            if _is_chinese_name(a['full_name']):
                names.append(a['full_name'])
            else:
                names.append(a['surname'])
        if len(authors) > n:
            return ', '.join(names) + ' et al.'
        return ', '.join(names)
    
    elif format_type == 'n_full':
        names = [a['full_name'] for a in authors[:n]]
        if len(authors) > n:
            return ', '.join(names) + ' et al.'
        return ', '.join(names)
    
    return authors[0]['surname']  # Default fallback


def extract_first_page_text(pdf_path: str) -> Optional[str]:
    """Extract text from the first page of a PDF, with OCR fallback."""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            return None
        page = doc[0]
        text = page.get_text()
        doc.close()

        if len(text.strip()) < OCR_MIN_TEXT_LENGTH:
            ocr_text = _extract_text_with_ocr(pdf_path, max_pages=1)
            if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                return ocr_text

        return text
    except Exception as e:
        logger.error(f"Error reading {pdf_path}: {e}")
        return None


def extract_multi_page_text(pdf_path: str, max_pages: int = 3) -> Optional[str]:
    """Extract text from the first N pages of a PDF, with OCR fallback."""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            return None
        
        texts = []
        pages_to_read = min(len(doc), max_pages)
        for i in range(pages_to_read):
            page = doc[i]
            texts.append(page.get_text())
        
        doc.close()
        combined = '\n'.join(texts)

        if len(combined.strip()) < OCR_MIN_TEXT_LENGTH:
            ocr_text = _extract_text_with_ocr(pdf_path, max_pages=max_pages)
            if ocr_text and len(ocr_text.strip()) > len(combined.strip()):
                return ocr_text

        return combined
    except Exception as e:
        logger.error(f"Error reading multi-page from {pdf_path}: {e}")
        return None


def extract_text_blocks_with_font(pdf_path: str) -> list:
    """Extract text blocks with font information to help identify title vs authors."""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            return []
        page = doc[0]
        blocks = page.get_text("dict")["blocks"]
        doc.close()
        
        result = []
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    text = ""
                    max_font_size = 0
                    for span in line["spans"]:
                        text += span["text"]
                        max_font_size = max(max_font_size, span["size"])
                    if text.strip():
                        result.append({
                            "text": text.strip(),
                            "font_size": max_font_size,
                            "y": line["bbox"][1]  # y position
                        })
        return result
    except Exception as e:
        logger.error(f"Error extracting blocks from {pdf_path}: {e}")
        return []


def parse_aaai_paper_info(pdf_path: str, directory_name: str) -> Tuple[Optional[str], list, int]:
    """
    Parse AAAI paper to extract title, authors, and year.
    
    Returns: (title, authors_list, year)
    """
    # Fallback year from directory name
    fallback_year = AAAI_YEAR_MAP.get(directory_name, 2023)
    
    # Try to extract text blocks with font info from first page
    blocks = extract_text_blocks_with_font(pdf_path)
    
    if not blocks:
        return None, [], fallback_year
    
    # Collect first page text for year extraction
    first_page_text = ' '.join([b["text"] for b in blocks])
    
    # Try to extract year from first page
    year = extract_year_from_text(first_page_text)
    
    # If not found on first page, search in first 3 pages
    if not year:
        multi_page_text = extract_multi_page_text(pdf_path, max_pages=3)
        if multi_page_text:
            year = extract_year_from_text(multi_page_text)
    
    if not year:
        year = fallback_year
    
    # Filter out conference header lines (usually contains "AAAI" or "Conference")
    # The title is typically the largest font text after the header
    # Authors come after the title, usually in smaller but still prominent font
    
    title = None
    authors_text = None
    
    # Find the title (largest font, excluding headers)
    # Skip lines that look like conference headers
    header_patterns = [
        r'AAAI',
        r'Conference',
        r'Association for',
        r'Artificial Intelligence',
        r'Copyright',
        r'www\.',
        r'http',
    ]
    
    # Find candidate title and author blocks
    content_blocks = []
    for block in blocks:
        text = block["text"]
        # Skip header/footer content
        is_header = any(re.search(pat, text, re.IGNORECASE) for pat in header_patterns)
        if is_header:
            continue
        # Skip very short lines (likely noise)
        if len(text) < 5:
            continue
        # Skip lines that look like emails
        if '@' in text and ' ' not in text:
            continue
        content_blocks.append(block)
    
    if not content_blocks:
        return None, [], year
    
    # Sort by font size (descending) to find title
    sorted_by_font = sorted(content_blocks, key=lambda x: x["font_size"], reverse=True)
    
    # The title should be among the largest fonts
    if sorted_by_font:
        # Title is typically the largest
        title = sorted_by_font[0]["text"]
        title_y = sorted_by_font[0]["y"]
        title_font_size = sorted_by_font[0]["font_size"]
        
        # Sometimes title spans multiple lines - try to combine
        for block in sorted_by_font[1:]:
            # If same font size and close vertically, might be part of title
            if abs(block["font_size"] - title_font_size) < 1 and block["y"] > title_y:
                if block["y"] - title_y < 30:  # Close vertically
                    title = title + " " + block["text"]
                    title_y = block["y"]
        
        # Find authors - should be after title, smaller font but still visible
        for block in content_blocks:
            if block["y"] > title_y:
                text = block["text"]
                # Authors line typically contains names (commas, possibly *)
                # and NOT keywords like "Abstract", "Introduction", etc.
                if any(kw in text.lower() for kw in ['abstract', 'introduction', 'keyword', 'department', 'university', 'college', 'school', 'institute', '{', '@']):
                    continue
                # Check if it looks like author names (contains commas or has typical name patterns)
                # Author lines often have asterisks for corresponding author
                if ',' in text or '*' in text:
                    authors_text = text
                    break
                # Or check if it contains multiple capitalized words (names)
                name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+'
                if re.search(name_pattern, text):
                    authors_text = text
                    break
    
    # Parse authors list
    authors = []
    if authors_text:
        authors = parse_all_authors(authors_text)
    
    return title, authors, year


def fallback_parse_from_text(pdf_path: str, directory_name: str) -> Tuple[Optional[str], list, int]:
    """Fallback parsing using simple text extraction."""
    fallback_year = AAAI_YEAR_MAP.get(directory_name, 2023)
    text = extract_first_page_text(pdf_path)
    
    if not text:
        return None, [], fallback_year
    
    # Extract year from first page
    year = extract_year_from_text(text)
    
    # If not found, try first 3 pages
    if not year:
        multi_page_text = extract_multi_page_text(pdf_path, max_pages=3)
        if multi_page_text:
            year = extract_year_from_text(multi_page_text)
    
    if not year:
        year = fallback_year
    
    # Try Chinese thesis/dissertation parsing first
    result = _try_parse_chinese_thesis(text, year)
    if result:
        return result
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Skip conference/journal header lines
    content_lines = []
    skip_patterns = [
        r'AAAI',
        r'Conference',
        r'Association',
        r'Copyright',
        r'www\.',
        r'https?://',
        r'ScienceDirect',
        r'Elsevier',
        r'Springer',
        r'journal\s+homepage',
        r'Contents\s+lists?\s+available',
        r'Check\s+for',
        r'^\s*updates?\s*$',
        r'ARTICLE\s+INFO',
        r'Keywords?:',
        r'^\d+[-–]\d+$',  # Page ranges like "105216"
        r'^[A-Z]{3,}\s*$',  # All-caps short strings like "SFOSCIENC"
    ]
    
    for line in lines:
        if any(re.search(pat, line, re.IGNORECASE) for pat in skip_patterns):
            continue
        if len(line) < 5:
            continue
        content_lines.append(line)
    
    if len(content_lines) < 2:
        return None, [], year
    
    # Look for the title: prefer lines that look like paper titles
    # (natural language, substantial length, no metadata markers)
    title = None
    title_idx = 0
    
    # Among first 6 content lines, pick the one that looks most like a title
    best_score = -1
    for i, line in enumerate(content_lines[:6]):
        score = len(line)
        # Position penalty: titles appear early; later lines are more likely body text
        score -= i * 15
        # Penalize lines with colons (likely metadata)
        if ':' in line:
            score -= 50
        # Penalize lines that are mostly digits
        digit_ratio = sum(1 for c in line if c.isdigit()) / max(len(line), 1)
        if digit_ratio > 0.3:
            score -= 80
        # Penalize very short lines
        if len(line) < 20:
            score -= 30
        # Penalize lines with parenthesized year/volume info
        if re.search(r'\(\d{4}\)', line):
            score -= 40
        # Penalize lines with institutional/address words
        address_words = ['department', 'university', 'college', 'school', 'institute',
                         'street', 'avenue', 'road', 'united kingdom', 'united states',
                         'china', 'japan', 'korea', 'canada', 'australia', 'france',
                         'germany', 'india', 'brazil', 'italy', 'spain',
                         'laboratory', 'lab ', 'faculty']
        if any(kw in line.lower() for kw in address_words):
            score -= 100
        # Penalize lines that look like journal names (short capitalized phrases)
        if re.match(r'^[A-Z][a-z]+(\s+(and|&|of|in|for)\s+[A-Z][a-z]+)*\s*$', line):
            score -= 40
        # Penalize lines with commas and asterisks (likely author lines)
        if ('*' in line or '∗' in line) and ',' in line:
            score -= 60
        # Bonus for lines that look like academic titles (lowercase words, moderate length)
        lowercase_ratio = sum(1 for c in line if c.islower()) / max(len(line), 1)
        if lowercase_ratio > 0.5 and len(line) > 30:
            score += 20
        if score > best_score:
            best_score = score
            title = line
            title_idx = i
    
    # Try to find authors in lines after the title
    authors = []
    for line in content_lines[title_idx+1:title_idx+6]:
        # Skip if looks like abstract or section
        if any(kw in line.lower() for kw in ['abstract', 'introduction', 'we ', 'this paper']):
            break
        # Skip institution/affiliation lines
        if any(kw in line.lower() for kw in ['department', 'university', 'college', 'school', 'institute']):
            continue
        # Look for name-like patterns (commas suggest multiple authors)
        if ',' in line or '*' in line or re.search(r'\b[A-Z]\.\w?\.\s*[A-Z]', line) or re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', line):
            authors = parse_all_authors(line)
            if authors:
                break
    
    return title, authors, year


def _try_parse_chinese_thesis(text: str, year: int) -> Optional[Tuple[str, list, int]]:
    """Try to parse text as a Chinese thesis/dissertation with labeled fields."""
    # Look for explicit title label: 论文题目, 题目, 题 目
    title_match = re.search(r'(?:论文题目|题\s*目)[：:\s]*(.+)', text)
    if not title_match:
        return None
    
    title = title_match.group(1).strip()
    # Clean up: if the title continues with an English translation on next line, take just the Chinese
    # Also strip trailing labels
    title = re.split(r'\n', title)[0].strip()
    if not title:
        return None
    
    # Look for author label: 作者姓名, 作者, 姓名
    author_match = re.search(r'(?:作者姓名|作\s*者)[：:\s]*(.+)', text)
    authors = []
    if author_match:
        author_str = author_match.group(1).strip().split('\n')[0].strip()
        # Chinese names: 2-4 CJK characters
        cn_names = re.findall(r'[\u4e00-\u9fff]{2,4}', author_str)
        if cn_names:
            for name in cn_names:
                authors.append({
                    'full_name': name,
                    'surname': name[0]
                })
    
    return title, authors, year


def is_valid_authors_list(authors: list) -> bool:
    """Check if the extracted authors list is valid."""
    if not authors:
        return False
    # Check at least the first author has a valid name
    first = authors[0]
    name = first.get('surname', '')
    if not name:
        return False
    # Allow single CJK character surnames (Chinese names)
    if len(name) == 1 and '\u4e00' <= name <= '\u9fff':
        return True
    if len(name) < 2:
        return False
    # Must be mostly alphabetic (or CJK)
    alpha_count = sum(1 for c in name if c.isalpha())
    if alpha_count < len(name) * 0.7:
        return False
    # Must start with a letter
    if not name[0].isalpha():
        return False
    # Should not be common non-name words
    invalid_names = {'the', 'and', 'for', 'with', 'from', 'abstract', 'introduction'}
    if name.lower() in invalid_names:
        return False
    return True


def generate_citation_filename(title: str, authors: list, year: int, 
                               author_format: str = 'first_surname', n: int = 3) -> str:
    """Generate citation-style filename: 'Author(s) (Year) - Title.pdf'"""
    title_clean = sanitize_filename(title)
    
    author_str = format_authors_for_filename(authors, author_format, n)
    if not author_str:
        author_str = "Unknown"
    author_clean = sanitize_filename(author_str)
    
    # Add "et al." only for single-author formats when there are multiple authors
    if author_format in ['first_surname', 'first_full'] and len(authors) > 1:
        return f"{author_clean} et al. ({year}) - {title_clean}.pdf"
    else:
        return f"{author_clean} ({year}) - {title_clean}.pdf"


def process_directory(base_dir: str, dry_run: bool = True, 
                      author_format: str = 'first_surname', n_authors: int = 3):
    """Process all PDF files in base_dir and all its subdirectories recursively."""
    base_path = Path(base_dir)
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    results = []  # Store results for summary
    
    # Collect all PDFs: base directory + every subdirectory
    pdf_files = sorted(base_path.rglob('*.pdf'))
    
    if not pdf_files:
        logger.warning(f"No PDF files found under: {base_path}")
        return results
    
    logger.info(f"Found {len(pdf_files)} PDF files under {base_path}")
    
    for pdf_path in pdf_files:
        try:
            # Use parent directory name for fallback year lookup
            subdir_name = pdf_path.parent.name if pdf_path.parent != base_path else ''
            
            # First try structured extraction
            title, authors, year = parse_aaai_paper_info(str(pdf_path), subdir_name)
            
            # Fallback if structured extraction failed
            if not title or not authors:
                title, authors, year = fallback_parse_from_text(str(pdf_path), subdir_name)
            
            if not title or not is_valid_authors_list(authors):
                author_info = authors[0]['surname'] if authors else 'None'
                logger.warning(f"Could not extract valid info from: {pdf_path.name} (author={author_info})")
                skip_count += 1
                results.append({
                    'original': pdf_path.name,
                    'status': 'SKIP',
                    'reason': f'Invalid extraction: author={author_info}'
                })
                continue
            
            # Generate new filename
            new_filename = generate_citation_filename(title, authors, year, author_format, n_authors)
            new_path = pdf_path.parent / new_filename
            
            # Check if file already has correct name
            if pdf_path.name == new_filename:
                logger.info(f"Already named correctly: {pdf_path.name}")
                skip_count += 1
                continue
            
            # Handle duplicate names
            if new_path.exists() and new_path != pdf_path:
                counter = 2
                while new_path.exists():
                    base_name = new_filename[:-4]  # Remove .pdf
                    new_filename = f"{base_name} ({counter}).pdf"
                    new_path = pdf_path.parent / new_filename
                    counter += 1
            
            if dry_run:
                logger.info(f"[DRY RUN] Would rename:\n  FROM: {pdf_path.name}\n  TO:   {new_filename}")
            else:
                pdf_path.rename(new_path)
                logger.info(f"Renamed: {pdf_path.name} -> {new_filename}")
            
            success_count += 1
            author_display = format_authors_for_filename(authors, author_format, n_authors)
            results.append({
                'original': pdf_path.name,
                'new': new_filename,
                'title': title,
                'authors': author_display,
                'year': year,
                'status': 'OK'
            })
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            error_count += 1
            results.append({
                'original': pdf_path.name,
                'status': 'ERROR',
                'reason': str(e)
            })
    
    # Print summary
    logger.info("=" * 60)
    logger.info(f"SUMMARY:")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Skipped: {skip_count}")
    logger.info(f"  Errors:  {error_count}")
    logger.info("=" * 60)
    
    return results


def main():
    import argparse
    
    # Build format choices help text
    format_help = "Author format options:\n"
    for key, desc in AUTHOR_FORMAT_OPTIONS.items():
        format_help += f"  {key}: {desc}\n"
    
    parser = argparse.ArgumentParser(
        description='Rename AAAI papers to citation format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=format_help
    )
    parser.add_argument('--dir', '-d', default='.', 
                        help='Base directory containing AAAI_37, AAAI_38, AAAI_39 folders')
    parser.add_argument('--dry-run', '-n', action='store_true', default=True,
                        help='Show what would be renamed without actually renaming (default: True)')
    parser.add_argument('--execute', '-x', action='store_true',
                        help='Actually execute the renames (disables dry-run)')
    parser.add_argument('--format', '-f', 
                        choices=list(AUTHOR_FORMAT_OPTIONS.keys()),
                        default='first_surname',
                        help='Author name format (default: first_surname)')
    parser.add_argument('--num-authors', '-N', type=int, default=3,
                        help='Number of authors for n_surnames/n_full formats (default: 3)')
    parser.add_argument('--limit', '-l', type=int, default=None,
                        help='Limit processing to first N files (for testing)')
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    # Show selected format
    logger.info(f"Author format: {args.format} - {AUTHOR_FORMAT_OPTIONS[args.format]}")
    if args.format in ['n_surnames', 'n_full']:
        logger.info(f"Number of authors: {args.num_authors}")
    
    if dry_run:
        logger.info("DRY RUN MODE - No files will be renamed")
        logger.info("Use --execute or -x flag to actually rename files")
    else:
        logger.info("EXECUTE MODE - Files will be renamed!")
        response = input("Are you sure you want to rename files? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Aborted by user")
            return
    
    base_dir = Path(args.dir).resolve()
    logger.info(f"Processing directory: {base_dir}")
    
    results = process_directory(
        str(base_dir), 
        dry_run=dry_run,
        author_format=args.format,
        n_authors=args.num_authors
    )
    
    # Save results to CSV
    results_file = base_dir / 'rename_results.csv'
    try:
        import csv
        with open(results_file, 'w', newline='', encoding='utf-8') as f:
            if results:
                writer = csv.DictWriter(f, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
        logger.info(f"Results saved to: {results_file}")
    except Exception as e:
        logger.error(f"Could not save results CSV: {e}")


if __name__ == '__main__':
    main()
