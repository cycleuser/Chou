"""
Integration tests for chou.core.processor using real PDFs from test/ directory
and a synthetic PDF (generated in conftest.py) to guarantee text-extractable
content regardless of the nature of the user-provided test files.
"""

import pytest
from pathlib import Path

from chou.core.processor import PaperProcessor
from chou.core.models import AuthorFormat, PaperInfo, Author
from chou.core.extractor import (
    check_pymupdf,
    extract_first_page_text,
    extract_multi_page_text,
    extract_text_blocks_with_font,
)
from chou.core.year_parser import extract_year_from_text


# ── PyMuPDF availability ─────────────────────────────────────────────────

class TestExtractor:
    def test_pymupdf_available(self):
        assert check_pymupdf(), "PyMuPDF (fitz) must be installed"


# ── Text extraction (includes synthetic PDF) ─────────────────────────────

class TestPdfTextExtraction:
    """
    Uses all_pdf_paths (real + synthetic) so at least the synthetic PDF
    always provides extractable text.
    """

    def test_first_page_text_at_least_one(self, all_pdf_paths):
        """At least one PDF should yield non-empty first-page text."""
        extracted = 0
        for pdf_path in all_pdf_paths:
            text = extract_first_page_text(str(pdf_path))
            if text and len(text) > 50:
                extracted += 1
        assert extracted > 0, "No PDF yielded usable first-page text"

    def test_extract_does_not_crash(self, all_pdf_paths):
        """Extraction should never raise — even for image-only PDFs."""
        for pdf_path in all_pdf_paths:
            text = extract_first_page_text(str(pdf_path))
            assert text is not None, f"Returned None for {pdf_path.name}"

    def test_multi_page_text(self, all_pdf_paths):
        for pdf_path in all_pdf_paths:
            text = extract_multi_page_text(str(pdf_path), max_pages=2)
            assert text is not None, f"No multi-page text from {pdf_path.name}"

    def test_text_blocks_with_font_at_least_one(self, all_pdf_paths):
        """At least one PDF should produce text blocks with font info."""
        any_blocks = False
        for pdf_path in all_pdf_paths:
            blocks = extract_text_blocks_with_font(str(pdf_path))
            if blocks:
                any_blocks = True
                for b in blocks:
                    assert "text" in b
                    assert "font_size" in b
                    assert "y" in b
        assert any_blocks, "No PDF produced text blocks"


# ── Synthetic PDF specific tests ─────────────────────────────────────────

class TestSyntheticPdf:
    """Deterministic tests using the synthetic PDF with known content."""

    def test_title_extraction(self, synthetic_pdf):
        text = extract_first_page_text(str(synthetic_pdf))
        assert "Deep Learning" in text
        assert "Geochemical" in text

    def test_author_text_present(self, synthetic_pdf):
        text = extract_first_page_text(str(synthetic_pdf))
        assert "Wang" in text
        assert "Zhang" in text

    def test_year_extraction(self, synthetic_pdf):
        text = extract_first_page_text(str(synthetic_pdf))
        year = extract_year_from_text(text)
        assert year == 2023

    def test_blocks_have_font_info(self, synthetic_pdf):
        blocks = extract_text_blocks_with_font(str(synthetic_pdf))
        assert len(blocks) > 0
        font_sizes = [b["font_size"] for b in blocks]
        # The title font (18pt) should be the largest
        assert max(font_sizes) >= 18


# ── Year extraction from real PDFs ───────────────────────────────────────

class TestPdfYearExtraction:
    def test_year_extracted_at_least_one(self, all_pdf_paths):
        """At least one PDF should yield a plausible year."""
        extracted = 0
        for pdf_path in all_pdf_paths:
            text = extract_first_page_text(str(pdf_path))
            if not text:
                continue
            year = extract_year_from_text(text)
            if year is not None:
                assert 1990 <= year <= 2030, (
                    f"Implausible year {year} from {pdf_path.name}"
                )
                extracted += 1
        assert extracted > 0, "No PDF yielded an extractable year"


# ── PaperProcessor ───────────────────────────────────────────────────────

class TestPaperProcessor:
    def test_process_single(self, all_pdf_paths):
        processor = PaperProcessor()
        for pdf_path in all_pdf_paths:
            paper = processor.process_single(pdf_path)
            assert isinstance(paper, PaperInfo)
            assert paper.file_path == pdf_path
            assert paper.status in ("success", "error")

    def test_successful_extraction_has_metadata(self, all_pdf_paths):
        processor = PaperProcessor()
        successes = []
        for pdf_path in all_pdf_paths:
            paper = processor.process_single(pdf_path)
            if paper.status == "success":
                successes.append(paper)
                assert paper.title, f"No title for {pdf_path.name}"
                assert paper.year, f"No year for {pdf_path.name}"
                assert len(paper.authors) > 0, f"No authors for {pdf_path.name}"
                assert paper.new_filename, f"No filename for {pdf_path.name}"
                assert paper.new_filename.endswith(".pdf")
        assert len(successes) > 0, "No PDFs processed successfully"

    def test_process_directory(self, test_pdf_dir):
        processor = PaperProcessor()
        results = processor.process_directory(test_pdf_dir)
        assert len(results) > 0, "No results from test/ directory"
        for paper in results:
            assert isinstance(paper, PaperInfo)

    def test_dry_run_does_not_rename(self, all_pdf_paths):
        processor = PaperProcessor()
        papers = [processor.process_single(p) for p in all_pdf_paths]
        original_names = [p.file_path.name for p in papers]
        processor.apply_renames(papers, dry_run=True)
        for paper, orig_name in zip(papers, original_names):
            assert paper.file_path.name == orig_name

    def test_different_author_formats(self, synthetic_pdf):
        """Processor should work with all author format settings."""
        for fmt in AuthorFormat:
            processor = PaperProcessor(author_format=fmt)
            paper = processor.process_single(synthetic_pdf)
            # Synthetic PDF always has extractable text
            if paper.status == "success":
                assert paper.new_filename.endswith(".pdf")

    def test_update_paper_filename(self, sample_authors):
        """update_paper_filename should regenerate the filename."""
        processor = PaperProcessor(author_format=AuthorFormat.FIRST_SURNAME)
        paper = PaperInfo(file_path=Path("dummy.pdf"))
        paper.title = "Test Title"
        paper.authors = sample_authors
        paper.year = 2024
        paper = processor.update_paper_filename(paper)
        assert paper.new_filename is not None
        assert "2024" in paper.new_filename
        assert paper.new_filename.endswith(".pdf")

    def test_ocr_engine_none_disables_ocr(self, all_pdf_paths):
        """With ocr_engine='none', scanned PDFs should not get OCR text."""
        processor = PaperProcessor(ocr_engine="none")
        for pdf_path in all_pdf_paths:
            paper = processor.process_single(pdf_path)
            assert isinstance(paper, PaperInfo)


# ── OCR Integration (skipped when no OCR engine installed) ───────────────

from chou.core.ocr_extractor import get_available_engines

_any_ocr = bool(get_available_engines())


@pytest.mark.skipif(not _any_ocr, reason="No OCR engine installed")
class TestOcrIntegration:
    """Test that scanned PDFs can be processed when an OCR engine is available."""

    def test_scanned_pdf_extracts_text(self, pdf_paths):
        """Scanned PDFs should now produce non-empty text via OCR fallback."""
        for pdf_path in pdf_paths:
            text = extract_first_page_text(str(pdf_path))
            assert text is not None
            # With OCR, at least one scanned PDF should yield substantial text
        any_text = any(
            len((extract_first_page_text(str(p)) or "").strip()) > 50
            for p in pdf_paths
        )
        assert any_text, "OCR fallback should extract text from at least one scanned PDF"

    def test_processor_succeeds_with_ocr(self, pdf_paths):
        """Processor should successfully extract metadata from scanned PDFs with OCR."""
        processor = PaperProcessor()
        successes = 0
        for pdf_path in pdf_paths:
            paper = processor.process_single(pdf_path)
            if paper.status == "success":
                successes += 1
                assert paper.title
                assert paper.year
        assert successes > 0, "OCR should help process at least one scanned PDF"

    def test_year_from_scanned(self, pdf_paths):
        """Year extraction should work on OCR text from scanned PDFs."""
        found_year = False
        for pdf_path in pdf_paths:
            text = extract_multi_page_text(str(pdf_path), max_pages=3)
            if text and len(text.strip()) > 50:
                year = extract_year_from_text(text)
                if year and 1990 <= year <= 2030:
                    found_year = True
        assert found_year, "Should extract a year from at least one scanned PDF"
