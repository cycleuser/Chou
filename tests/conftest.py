"""
Shared pytest fixtures for Chou test suite.

Uses the `test/` directory as the source for PDF test fixtures.
A synthetic PDF with known metadata is also generated so that
integration tests always have at least one text-extractable file.
"""

import pytest
from pathlib import Path

import fitz  # PyMuPDF

from chou.core.models import Author, AuthorFormat, PaperInfo


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_PDF_DIR = PROJECT_ROOT / "test"


@pytest.fixture
def test_pdf_dir():
    """Return the path to the test/ directory containing sample PDFs."""
    return TEST_PDF_DIR


@pytest.fixture
def pdf_paths(test_pdf_dir):
    """Return a list of all PDF paths found in test/."""
    if not test_pdf_dir.exists():
        pytest.skip("test/ directory not found")
    paths = sorted(test_pdf_dir.glob("*.pdf"))
    if not paths:
        pytest.skip("No PDF files in test/ directory")
    return paths


# ---------------------------------------------------------------------------
# Synthetic PDF with known metadata (always text-extractable)
# ---------------------------------------------------------------------------

_SYNTH_TITLE = "Deep Learning for Geochemical Anomaly Detection"
_SYNTH_AUTHORS = "Weihao Wang, Rufeng Zhang, Mingyu You"
_SYNTH_YEAR_LINE = "Copyright © 2023 AAAI"

@pytest.fixture
def synthetic_pdf(tmp_path):
    """
    Create a one-page PDF in a temp directory with known title, author
    and year text so integration tests always have extractable content.
    Returns the Path to the generated PDF.
    """
    pdf_path = tmp_path / "synthetic_paper.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # Title — large font at the top
    page.insert_text((72, 80), _SYNTH_TITLE, fontsize=18)
    # Authors — medium font below title
    page.insert_text((72, 120), _SYNTH_AUTHORS, fontsize=12)
    # Year / copyright — smaller font
    page.insert_text((72, 160), _SYNTH_YEAR_LINE, fontsize=10)
    # Some body text
    page.insert_text((72, 200),
        "Abstract: This paper presents a novel approach to geochemical "
        "anomaly detection using deep learning techniques.",
        fontsize=10,
    )

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def all_pdf_paths(pdf_paths, synthetic_pdf):
    """
    Combine real PDFs from test/ with the synthetic PDF.
    Guarantees at least one text-extractable file.
    """
    return pdf_paths + [synthetic_pdf]


# ---------------------------------------------------------------------------
# Author fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_authors():
    """Three sample Author objects for formatting tests."""
    return [
        Author(full_name="Weihao Wang", surname="Wang"),
        Author(full_name="Rufeng Zhang", surname="Zhang"),
        Author(full_name="Mingyu You", surname="You"),
    ]


@pytest.fixture
def single_author():
    """A single Author object."""
    return [Author(full_name="John Smith", surname="Smith")]


@pytest.fixture
def many_authors():
    """Six authors — triggers truncation in some format modes."""
    return [
        Author(full_name="Alice Adams", surname="Adams"),
        Author(full_name="Bob Brown", surname="Brown"),
        Author(full_name="Carol Clark", surname="Clark"),
        Author(full_name="Dave Davis", surname="Davis"),
        Author(full_name="Eve Evans", surname="Evans"),
        Author(full_name="Frank Foster", surname="Foster"),
    ]
