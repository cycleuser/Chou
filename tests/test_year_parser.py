"""
Tests for chou.core.year_parser
"""

import pytest

from chou.core.year_parser import (
    chinese_year_to_int,
    edition_to_year,
    extract_year_from_text,
)


# ── chinese_year_to_int ──────────────────────────────────────────────────

class TestChineseYearToInt:
    @pytest.mark.parametrize("cn, expected", [
        ("二〇二三", 2023),
        ("二零二四", 2024),
        ("一九九九", 1999),
        ("二〇〇〇", 2000),
        ("二〇二五", 2025),
    ])
    def test_valid_conversions(self, cn, expected):
        assert chinese_year_to_int(cn) == expected

    @pytest.mark.parametrize("cn", [
        "",          # empty
        "二〇",      # too short
        "abc",       # non-Chinese
        "二〇二",    # only 3 digits
    ])
    def test_invalid_returns_none(self, cn):
        assert chinese_year_to_int(cn) is None


# ── edition_to_year ──────────────────────────────────────────────────────

class TestEditionToYear:
    def test_aaai_edition(self):
        assert edition_to_year(37, "AAAI") == 2023
        assert edition_to_year(38, "AAAI") == 2024
        assert edition_to_year(39, "AAAI") == 2025

    def test_default_conference_recent(self):
        # edition < 50 → 2000 + edition
        assert edition_to_year(23, "CVPR") == 2023

    def test_default_conference_old(self):
        # edition >= 50 → 1900 + edition
        assert edition_to_year(99, "CVPR") == 1999


# ── extract_year_from_text ───────────────────────────────────────────────

class TestExtractYearFromText:

    def test_empty_text(self):
        assert extract_year_from_text("") is None
        assert extract_year_from_text(None) is None

    # Strategy 1: Conference abbreviation with year
    @pytest.mark.parametrize("text, expected", [
        ("The Thirty-Seventh AAAI Conference on Artificial Intelligence (AAAI-23)", 2023),
        ("CVPR 2024", 2024),
        ("NeurIPS'22", 2022),
        ("ICML 2023 Proceedings", 2023),
        ("2025 AAAI", 2025),
    ])
    def test_conference_year(self, text, expected):
        assert extract_year_from_text(text) == expected

    # Strategy 3: Copyright notice
    @pytest.mark.parametrize("text, expected", [
        ("Copyright © 2023 AAAI", 2023),
        ("Copyright 2024 IEEE", 2024),
        ("© 2022 Elsevier Ltd.", 2022),
    ])
    def test_copyright(self, text, expected):
        assert extract_year_from_text(text) == expected

    # Strategy 4: Published / Accepted dates
    @pytest.mark.parametrize("text, expected", [
        ("Published: March 2024", 2024),
        ("Accepted: January 15, 2024", 2024),
        ("Received: September 2023", 2023),
    ])
    def test_published_dates(self, text, expected):
        assert extract_year_from_text(text) == expected

    # Strategy 4b: Chinese publication dates
    @pytest.mark.parametrize("text, expected", [
        ("收稿日期: 2024-01-15", 2024),
        ("发表于 2023", 2023),
        ("出版日期: 2022", 2022),
    ])
    def test_chinese_pub_dates(self, text, expected):
        assert extract_year_from_text(text) == expected

    # Strategy 5: Chinese year patterns
    @pytest.mark.parametrize("text, expected", [
        ("2023年3月发表", 2023),
        ("二〇二三年", 2023),
    ])
    def test_chinese_year_patterns(self, text, expected):
        assert extract_year_from_text(text) == expected

    # Strategy 6: Journal volume
    def test_journal_volume(self):
        assert extract_year_from_text("第35卷 2023") == 2023
        assert extract_year_from_text("Vol. 12, No. 3, 2022") == 2022

    # Strategy 7: arXiv identifier
    def test_arxiv_id(self):
        assert extract_year_from_text("arXiv:2301.12345") == 2023
        assert extract_year_from_text("arXiv:1912.00001") == 2019

    # Strategy 8: DOI with year
    def test_doi_year(self):
        assert extract_year_from_text("10.1109/CVPR.2023.12345") == 2023

    # Strategy 9: Month-year date patterns
    def test_month_year(self):
        assert extract_year_from_text("March 2024") == 2024
        assert extract_year_from_text("15 January 2023") == 2023
