"""
PDF text extraction functions using PyMuPDF, with optional OCR fallback.
"""

from typing import Optional, List, Dict
import logging

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from .ocr_extractor import extract_text_with_ocr, get_available_engines, OCR_MIN_TEXT_LENGTH

logger = logging.getLogger(__name__)


def check_pymupdf() -> bool:
    """Check if PyMuPDF is available"""
    return fitz is not None


def extract_first_page_text(pdf_path: str, ocr_engine: Optional[str] = None, device: Optional[str] = None) -> Optional[str]:
    """
    Extract text from the first page of a PDF.
    Falls back to OCR if native extraction yields too little text.
    
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

        # OCR fallback for scanned / image-based PDFs
        if len(text.strip()) < OCR_MIN_TEXT_LENGTH and ocr_engine != "none":
            ocr_text = extract_text_with_ocr(pdf_path, max_pages=1, engine_name=ocr_engine, device=device)
            if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                return ocr_text

        return text
    except Exception as e:
        logger.error(f"Error reading {pdf_path}: {e}")
        return None


def extract_multi_page_text(pdf_path: str, max_pages: int = 3, ocr_engine: Optional[str] = None, device: Optional[str] = None) -> Optional[str]:
    """
    Extract text from the first N pages of a PDF for year extraction.
    Falls back to OCR if native extraction yields too little text.
    
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

        # OCR fallback for scanned / image-based PDFs
        if len(combined.strip()) < OCR_MIN_TEXT_LENGTH and ocr_engine != "none":
            ocr_text = extract_text_with_ocr(pdf_path, max_pages=max_pages, engine_name=ocr_engine, device=device)
            if ocr_text and len(ocr_text.strip()) > len(combined.strip()):
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
