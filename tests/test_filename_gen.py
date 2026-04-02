"""
Tests for chou.core.filename_gen
"""

import pytest

from chou.core.filename_gen import (
    sanitize_filename,
    format_authors_for_filename,
    generate_citation_filename,
)
from chou.core.models import Author, AuthorFormat


# ── sanitize_filename ────────────────────────────────────────────────────

class TestSanitizeFilename:
    @pytest.mark.parametrize("raw, expected", [
        ("Normal Title", "Normal Title"),
        ("Title: With Colon", "Title With Colon"),
        ("Title/With/Slashes", "TitleWithSlashes"),
        ("Title  With   Spaces", "Title With Spaces"),
        ("Title<With>Special*Chars?", "TitleWithSpecialChars"),
    ])
    def test_sanitize(self, raw, expected):
        assert sanitize_filename(raw) == expected

    def test_truncation(self):
        long_name = "A" * 300
        assert len(sanitize_filename(long_name)) == 200

    def test_strips_whitespace(self):
        assert sanitize_filename("  hello  ") == "hello"


# ── format_authors_for_filename ──────────────────────────────────────────

class TestFormatAuthorsForFilename:
    def test_first_surname(self, sample_authors):
        result = format_authors_for_filename(
            sample_authors, AuthorFormat.FIRST_SURNAME
        )
        assert result == "Wang"

    def test_first_full(self, sample_authors):
        result = format_authors_for_filename(
            sample_authors, AuthorFormat.FIRST_FULL
        )
        assert result == "Weihao Wang"

    def test_all_surnames(self, sample_authors):
        result = format_authors_for_filename(
            sample_authors, AuthorFormat.ALL_SURNAMES
        )
        assert result == "Wang, Zhang, You"

    def test_all_full(self, sample_authors):
        result = format_authors_for_filename(
            sample_authors, AuthorFormat.ALL_FULL
        )
        assert result == "Weihao Wang, Rufeng Zhang, Mingyu You"

    def test_n_surnames_with_et_al(self, sample_authors):
        result = format_authors_for_filename(
            sample_authors, AuthorFormat.N_SURNAMES, n=2
        )
        assert result == "Wang, Zhang et al."

    def test_n_full_with_et_al(self, sample_authors):
        result = format_authors_for_filename(
            sample_authors, AuthorFormat.N_FULL, n=2
        )
        assert result == "Weihao Wang, Rufeng Zhang et al."

    def test_n_surnames_no_et_al_when_n_covers_all(self, sample_authors):
        result = format_authors_for_filename(
            sample_authors, AuthorFormat.N_SURNAMES, n=5
        )
        # n >= len(authors) → no "et al."
        assert "et al." not in result

    def test_all_surnames_truncates_many(self, many_authors):
        result = format_authors_for_filename(
            many_authors, AuthorFormat.ALL_SURNAMES
        )
        # 6 authors > 5 → truncated to first 5 + "et al."
        assert "et al." in result
        assert result.count(",") == 4  # 5 names separated by 4 commas

    def test_empty_list_returns_none(self):
        assert format_authors_for_filename([], AuthorFormat.FIRST_SURNAME) is None


# ── generate_citation_filename ───────────────────────────────────────────

class TestGenerateCitationFilename:
    def test_basic_format(self, sample_authors):
        fname = generate_citation_filename(
            "Deep Learning Methods",
            sample_authors,
            2023,
            AuthorFormat.FIRST_SURNAME,
        )
        assert fname == "Wang et al. (2023) - Deep Learning Methods.pdf"

    def test_single_author_no_et_al(self, single_author):
        fname = generate_citation_filename(
            "A Great Paper",
            single_author,
            2024,
            AuthorFormat.FIRST_SURNAME,
        )
        assert fname == "Smith (2024) - A Great Paper.pdf"
        assert "et al." not in fname

    def test_all_surnames_no_extra_et_al(self, sample_authors):
        fname = generate_citation_filename(
            "Title",
            sample_authors,
            2023,
            AuthorFormat.ALL_SURNAMES,
        )
        # ALL_SURNAMES with 3 authors (<=5) → no extra "et al." wrapper
        assert fname == "Wang, Zhang, You (2023) - Title.pdf"

    def test_no_authors_uses_unknown(self):
        fname = generate_citation_filename(
            "Orphan Paper", [], 2023, AuthorFormat.FIRST_SURNAME
        )
        assert "Unknown" in fname

    def test_special_chars_cleaned(self, single_author):
        fname = generate_citation_filename(
            "Title: With <Special> Chars?",
            single_author,
            2024,
            AuthorFormat.FIRST_SURNAME,
        )
        assert ":" not in fname
        assert "<" not in fname
        assert "?" not in fname
    
    def test_very_long_title_truncated(self, single_author):
        very_long_title = "A" * 500
        fname = generate_citation_filename(
            very_long_title,
            single_author,
            2023,
            AuthorFormat.FIRST_SURNAME,
        )
        assert len(fname) <= 200
        assert fname.endswith(".pdf")
        assert "Smith (2023)" in fname
    
    def test_multiple_authors_very_long_title(self, sample_authors):
        very_long_title = "B" * 500
        fname = generate_citation_filename(
            very_long_title,
            sample_authors,
            2023,
            AuthorFormat.FIRST_SURNAME,
        )
        assert len(fname) <= 200
        assert fname.endswith(".pdf")
        assert "et al." in fname
        assert "(2023)" in fname
    
    def test_all_full_format_long_authors(self, many_authors):
        title = "Research Paper Title"
        fname = generate_citation_filename(
            title,
            many_authors,
            2023,
            AuthorFormat.ALL_FULL,
        )
        assert len(fname) <= 200
        assert fname.endswith(".pdf")
    
    def test_journal_included_long_filename(self, single_author):
        very_long_title = "C" * 300
        very_long_journal = "Journal of Very Long Name " * 10
        fname = generate_citation_filename(
            very_long_title,
            single_author,
            2023,
            include_journal=True,
            journal=very_long_journal,
        )
        assert len(fname) <= 200
        assert fname.endswith(".pdf")
