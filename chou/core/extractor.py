"""
PDF text extraction functions using PyMuPDF, with optional OCR fallback.

Improved Chinese text support:
- Detects corrupted Chinese characters (mojibake)
- Forces OCR when Chinese text extraction fails
- Better handling of Chinese PDFs with encoding issues
"""

from typing import Optional, List, Dict
import logging

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from .ocr_extractor import extract_text_with_ocr, OCR_MIN_TEXT_LENGTH
from ..utils.chinese_utils import (
    should_force_ocr_for_chinese,
    is_chinese_text_valid,
    count_cjk_chars,
    has_chinese_content,
)

logger = logging.getLogger(__name__)


def check_pymupdf() -> bool:
    """Check if PyMuPDF is available"""
    return fitz is not None


def extract_first_page_text(pdf_path: str, ocr_engine: Optional[str] = None, device: Optional[str] = None) -> Optional[str]:
    """
    Extract text from the first page of a PDF.
    Falls back to OCR if native extraction yields too little text
    or if Chinese text appears corrupted (mojibake).
    
    Args:
        pdf_path: Path to the PDF file
        ocr_engine: OCR engine name, None for auto-detect, "none" to disable
        device: Device preference: "cpu", "gpu", or None (auto)
        
    Returns:
        Text content of the first page, or None if extraction fails
    """
    if not fitz:
        logger.error("PyMuPDF not installed. Run: pip install PyMuPDF")
        return None
        
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            return None
        page = doc[0]
        text = page.get_text()
        doc.close()

        if ocr_engine == "none":
            return text

        cjk_count = count_cjk_chars(text)
        is_chinese_doc = cjk_count > 10

        needs_ocr = False
        ocr_reason = ""

        if len(text.strip()) < OCR_MIN_TEXT_LENGTH:
            needs_ocr = True
            ocr_reason = f"text_length={len(text.strip())} < {OCR_MIN_TEXT_LENGTH}"

        if is_chinese_doc and should_force_ocr_for_chinese(text):
            needs_ocr = True
            is_valid, reason = is_chinese_text_valid(text)
            ocr_reason = f"chinese_text_invalid: {reason}"

        if needs_ocr:
            logger.info(f"OCR fallback triggered for {pdf_path}: {ocr_reason}")
            ocr_text = extract_text_with_ocr(pdf_path, max_pages=1, engine_name=ocr_engine, device=device)
            if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                logger.info(f"OCR succeeded: {len(ocr_text.strip())} chars extracted (vs {len(text.strip())} from native)")
                return ocr_text
            elif ocr_text and is_chinese_doc:
                ocr_cjk_count = count_cjk_chars(ocr_text)
                if ocr_cjk_count > cjk_count:
                    logger.info(f"OCR better for Chinese: {ocr_cjk_count} CJK chars (vs {cjk_count} from native)")
                    return ocr_text

        return text
    except Exception as e:
        logger.error(f"Error reading {pdf_path}: {e}")
        return None


def extract_multi_page_text(pdf_path: str, max_pages: int = 3, ocr_engine: Optional[str] = None, device: Optional[str] = None) -> Optional[str]:
    """
    Extract text from the first N pages of a PDF for year extraction.
    Falls back to OCR if native extraction yields too little text
    or if Chinese text appears corrupted (mojibake).
    
    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to extract (default: 3)
        ocr_engine: OCR engine name, None for auto-detect, "none" to disable
        device: Device preference: "cpu", "gpu", or None (auto)
        
    Returns:
        Combined text content from pages, or None if extraction fails
    """
    if not fitz:
        logger.error("PyMuPDF not installed. Run: pip install PyMuPDF")
        return None
        
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            return None
        
        texts = []
        pages_to_read = min(len(doc), max_pages)
        for i in range(pages_to_read):
            page = doc[i]
            texts.append(page.get_text())
        
        doc.close()
        combined = '\n'.join(texts)

        if ocr_engine == "none":
            return combined

        cjk_count = count_cjk_chars(combined)
        is_chinese_doc = cjk_count > 20

        needs_ocr = False
        ocr_reason = ""

        if len(combined.strip()) < OCR_MIN_TEXT_LENGTH:
            needs_ocr = True
            ocr_reason = f"text_length={len(combined.strip())} < {OCR_MIN_TEXT_LENGTH}"

        if is_chinese_doc and should_force_ocr_for_chinese(combined):
            needs_ocr = True
            is_valid, reason = is_chinese_text_valid(combined)
            ocr_reason = f"chinese_text_invalid: {reason}"

        if needs_ocr:
            logger.info(f"OCR fallback triggered for {pdf_path}: {ocr_reason}")
            ocr_text = extract_text_with_ocr(pdf_path, max_pages=max_pages, engine_name=ocr_engine, device=device)
            if ocr_text and len(ocr_text.strip()) > len(combined.strip()):
                logger.info(f"OCR succeeded: {len(ocr_text.strip())} chars extracted")
                return ocr_text
            elif ocr_text and is_chinese_doc:
                ocr_cjk_count = count_cjk_chars(ocr_text)
                if ocr_cjk_count > cjk_count:
                    logger.info(f"OCR better for Chinese: {ocr_cjk_count} CJK chars (vs {cjk_count} from native)")
                    return ocr_text

        return combined
    except Exception as e:
        logger.error(f"Error reading multi-page from {pdf_path}: {e}")
        return None


def extract_text_blocks_with_font(pdf_path: str) -> List[Dict]:
    """
    Extract text blocks with font information to help identify title vs authors.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of dicts with 'text', 'font_size', and 'y' position
    """
    if not fitz:
        logger.error("PyMuPDF not installed. Run: pip install PyMuPDF")
        return []
        
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
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
