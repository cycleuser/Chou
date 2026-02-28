"""
Tests for chou.core.author_parser
"""

import pytest

from chou.core.author_parser import (
    clean_author_string,
    extract_name_words,
    parse_all_authors,
    is_valid_author,
    is_valid_authors_list,
)
from chou.core.models import Author


# ── clean_author_string ──────────────────────────────────────────────────

class TestCleanAuthorString:
    def test_removes_asterisks(self):
        result = clean_author_string("Weihao Wang*, Rufeng Zhang∗")
        assert "*" not in result
        assert "∗" not in result

    def test_removes_superscript_numbers(self):
        result = clean_author_string("Viet Dung Nguyen¹, Quan H. Nguyen²")
        assert "¹" not in result
        assert "²" not in result

    def test_removes_digits(self):
        result = clean_author_string("Alice1, Bob2, Carol3")
        # digits stripped, names remain
        assert "Alice" in result
        assert "Bob" in result

    def test_collapses_whitespace(self):
        result = clean_author_string("Alice   Bob   Carol")
        assert "  " not in result

    def test_empty_input(self):
        assert clean_author_string("") == ""


# ── extract_name_words ───────────────────────────────────────────────────

class TestExtractNameWords:
    def test_standard_name(self):
        assert extract_name_words("Weihao Wang") == ["Weihao", "Wang"]

    def test_ignores_lowercase(self):
        # "de" is all-lowercase → skipped
        words = extract_name_words("Jean de La Fontaine")
        assert "de" not in words
        assert "La" in words or "Jean" in words

    def test_short_tokens_skipped(self):
        # Single-letter tokens after stripping period are < 2 chars → skipped
        words = extract_name_words("H. Wang")
        assert "Wang" in words

    def test_empty(self):
        assert extract_name_words("") == []


# ── parse_all_authors ────────────────────────────────────────────────────

class TestParseAllAuthors:
    def test_standard_comma_list(self):
        authors = parse_all_authors(
            "Weihao Wang, Rufeng Zhang, Mingyu You"
        )
        surnames = [a.surname for a in authors]
        assert surnames == ["Wang", "Zhang", "You"]

    def test_with_markers(self):
        authors = parse_all_authors(
            "Weihao Wang*, Rufeng Zhang*, Mingyu You*"
        )
        surnames = [a.surname for a in authors]
        assert surnames == ["Wang", "Zhang", "You"]

    def test_with_superscripts(self):
        authors = parse_all_authors(
            "Viet Dung Nguyen *1, Quan H. Nguyen *2, Richard G. Freedman 3"
        )
        surnames = [a.surname for a in authors]
        assert surnames == ["Nguyen", "Nguyen", "Freedman"]

    def test_and_separator(self):
        authors = parse_all_authors("John Smith and Jane Doe")
        surnames = [a.surname for a in authors]
        assert surnames == ["Smith", "Doe"]

    def test_empty_input(self):
        assert parse_all_authors("") == []

    def test_returns_author_objects(self):
        authors = parse_all_authors("Alice Adams, Bob Brown")
        assert all(isinstance(a, Author) for a in authors)
        assert authors[0].full_name == "Alice Adams"


# ── is_valid_author / is_valid_authors_list ──────────────────────────────

class TestAuthorValidation:
    def test_valid_author(self):
        assert is_valid_author(Author(full_name="John Smith", surname="Smith"))

    def test_too_short(self):
        assert not is_valid_author(Author(full_name="X", surname="X"))

    def test_not_alpha_start(self):
        assert not is_valid_author(Author(full_name="123", surname="123"))

    def test_common_word_rejected(self):
        assert not is_valid_author(Author(full_name="abstract", surname="abstract"))

    def test_valid_list(self):
        authors = [Author(full_name="Alice Adams", surname="Adams")]
        assert is_valid_authors_list(authors)

    def test_empty_list(self):
        assert not is_valid_authors_list([])
