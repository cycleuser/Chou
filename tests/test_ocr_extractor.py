"""
Tests for chou.core.ocr_extractor — multi-backend OCR support.

Tests that depend on a specific OCR engine being installed are
conditionally skipped with @pytest.mark.skipif.
"""

import pytest

from chou.core.ocr_extractor import (
    get_available_engines,
    get_ocr_engine,
    extract_text_with_ocr,
    clear_engine_cache,
    ENGINE_PRIORITY,
    _ENGINE_CLASSES,
)


# ── Helpers ──────────────────────────────────────────────────────────────

_any_ocr = bool(get_available_engines())

skip_no_ocr = pytest.mark.skipif(
    not _any_ocr, reason="No OCR engine installed"
)


def _engine_available(name: str) -> bool:
    cls = _ENGINE_CLASSES.get(name)
    return cls is not None and cls.is_available()


# ── Engine discovery ─────────────────────────────────────────────────────

class TestEngineDiscovery:
    def test_get_available_engines_returns_list(self):
        engines = get_available_engines()
        assert isinstance(engines, list)
        for name in engines:
            assert name in ENGINE_PRIORITY

    def test_priority_order_preserved(self):
        engines = get_available_engines()
        if len(engines) >= 2:
            indices = [ENGINE_PRIORITY.index(e) for e in engines]
            assert indices == sorted(indices), "Engines should follow priority order"

    @skip_no_ocr
    def test_get_ocr_engine_auto(self):
        clear_engine_cache()
        engine = get_ocr_engine()
        assert engine is not None
        assert engine.name in ENGINE_PRIORITY

    def test_get_ocr_engine_invalid_name(self):
        engine = get_ocr_engine("nonexistent_engine")
        assert engine is None

    @skip_no_ocr
    def test_engine_caching(self):
        clear_engine_cache()
        e1 = get_ocr_engine()
        e2 = get_ocr_engine()
        assert e1 is e2, "Same engine instance should be returned (cached)"

    def test_clear_cache(self):
        clear_engine_cache()
        # Should not raise even if cache was empty


# ── Graceful degradation ─────────────────────────────────────────────────

class TestGracefulDegradation:
    def test_extract_returns_empty_when_no_engine(self, synthetic_pdf):
        """When engine_name is an invalid name, extraction returns empty."""
        text = extract_text_with_ocr(
            str(synthetic_pdf), max_pages=1, engine_name="nonexistent"
        )
        assert text == ""

    def test_extract_bad_path(self):
        text = extract_text_with_ocr("/nonexistent/path.pdf", max_pages=1)
        # Should not raise; returns empty string
        assert isinstance(text, str)


# ── Per-engine tests (skipped if that engine isn't installed) ────────────

class TestSuryaOcr:
    pytestmark = pytest.mark.skipif(
        not _engine_available("surya"), reason="surya-ocr not installed"
    )

    def test_ocr_scanned_pdf(self, pdf_paths):
        text = extract_text_with_ocr(
            str(pdf_paths[0]), max_pages=1, engine_name="surya"
        )
        assert len(text) > 20, "Surya should extract text from scanned PDF"

    def test_engine_name(self):
        engine = get_ocr_engine("surya")
        assert engine is not None
        assert engine.name == "surya"


class TestPaddleOcr:
    pytestmark = pytest.mark.skipif(
        not _engine_available("paddleocr"), reason="paddleocr not installed"
    )

    def test_ocr_scanned_pdf(self, pdf_paths):
        text = extract_text_with_ocr(
            str(pdf_paths[0]), max_pages=1, engine_name="paddleocr"
        )
        assert len(text) > 20, "PaddleOCR should extract text from scanned PDF"

    def test_engine_name(self):
        engine = get_ocr_engine("paddleocr")
        assert engine is not None
        assert engine.name == "paddleocr"


class TestRapidOcr:
    pytestmark = pytest.mark.skipif(
        not _engine_available("rapidocr"), reason="rapidocr not installed"
    )

    def test_ocr_scanned_pdf(self, pdf_paths):
        text = extract_text_with_ocr(
            str(pdf_paths[0]), max_pages=1, engine_name="rapidocr"
        )
        assert len(text) > 20, "RapidOCR should extract text from scanned PDF"

    def test_engine_name(self):
        engine = get_ocr_engine("rapidocr")
        assert engine is not None
        assert engine.name == "rapidocr"


class TestEasyOcr:
    pytestmark = pytest.mark.skipif(
        not _engine_available("easyocr"), reason="easyocr not installed"
    )

    def test_ocr_scanned_pdf(self, pdf_paths):
        text = extract_text_with_ocr(
            str(pdf_paths[0]), max_pages=1, engine_name="easyocr"
        )
        assert len(text) > 20, "EasyOCR should extract text from scanned PDF"

    def test_engine_name(self):
        engine = get_ocr_engine("easyocr")
        assert engine is not None
        assert engine.name == "easyocr"


class TestTesseract:
    pytestmark = pytest.mark.skipif(
        not _engine_available("tesseract"), reason="tesseract not installed"
    )

    def test_ocr_scanned_pdf(self, pdf_paths):
        text = extract_text_with_ocr(
            str(pdf_paths[0]), max_pages=1, engine_name="tesseract"
        )
        assert len(text) > 20, "Tesseract should extract text from scanned PDF"

    def test_engine_name(self):
        engine = get_ocr_engine("tesseract")
        assert engine is not None
        assert engine.name == "tesseract"


# ── Integration with real scanned PDFs ───────────────────────────────────

class TestOcrExtraction:
    pytestmark = skip_no_ocr

    def test_extract_from_scanned_english(self, pdf_paths):
        """First test PDF (ScienceDirect) should yield OCR text."""
        text = extract_text_with_ocr(str(pdf_paths[0]), max_pages=3)
        assert len(text) > 100, "OCR should extract substantial text"

    def test_extract_from_scanned_chinese(self, pdf_paths):
        """Second test PDF (Chinese thesis) should yield OCR text."""
        if len(pdf_paths) < 2:
            pytest.skip("Only one test PDF available")
        text = extract_text_with_ocr(str(pdf_paths[1]), max_pages=3)
        assert len(text) > 100, "OCR should extract text from Chinese PDF"

    def test_max_pages_respected(self, pdf_paths):
        text_1 = extract_text_with_ocr(str(pdf_paths[0]), max_pages=1)
        text_3 = extract_text_with_ocr(str(pdf_paths[0]), max_pages=3)
        # More pages should generally yield more text (or at least as much)
        assert len(text_3) >= len(text_1)
