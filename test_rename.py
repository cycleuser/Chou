#!/usr/bin/env python3
"""
Test script for rename_papers.py
Run: python test_rename.py
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    try:
        import fitz
        print("  [OK] PyMuPDF (fitz) installed")
    except ImportError:
        print("  [FAIL] PyMuPDF not installed. Run: pip install PyMuPDF")
        return False
    
    try:
        from rename_papers import (
            extract_year_from_text,
            chinese_year_to_int,
            clean_author_string,
            parse_all_authors,
            sanitize_filename,
            format_authors_for_filename,
            AUTHOR_FORMAT_OPTIONS,
        )
        print("  [OK] rename_papers.py imports successful")
    except ImportError as e:
        print(f"  [FAIL] Cannot import from rename_papers.py: {e}")
        return False
    
    return True


def test_year_extraction():
    """Test year extraction from various text formats."""
    print("\nTesting year extraction...")
    from rename_papers import extract_year_from_text
    
    test_cases = [
        # (input_text, expected_year, description)
        ("The Thirty-Seventh AAAI Conference on Artificial Intelligence (AAAI-23)", 2023, "AAAI-23 pattern"),
        ("CVPR 2024", 2024, "Conference + year"),
        ("NeurIPS'22", 2022, "Conference with apostrophe"),
        ("Copyright © 2023 AAAI", 2023, "Copyright notice"),
        ("Published: March 2024", 2024, "Published date"),
        ("arXiv:2301.12345", 2023, "arXiv ID"),
        ("2023年3月发表", 2023, "Chinese year pattern"),
        ("收稿日期: 2024-01-15", 2024, "Chinese received date"),
        ("第35卷 2023", 2023, "Chinese journal volume"),
        ("二〇二三年", 2023, "Chinese numeral year"),
        ("Accepted: January 15, 2024", 2024, "Accepted date with full format"),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected, desc in test_cases:
        result = extract_year_from_text(text)
        if result == expected:
            print(f"  [OK] {desc}: '{text[:40]}...' -> {result}")
            passed += 1
        else:
            print(f"  [FAIL] {desc}: '{text[:40]}...' -> {result} (expected {expected})")
            failed += 1
    
    print(f"  Year extraction: {passed}/{passed+failed} passed")
    return failed == 0


def test_chinese_year():
    """Test Chinese numeral year conversion."""
    print("\nTesting Chinese year conversion...")
    from rename_papers import chinese_year_to_int
    
    test_cases = [
        ("二〇二三", 2023),
        ("二零二四", 2024),
        ("一九九九", 1999),
        ("二〇〇〇", 2000),
    ]
    
    passed = 0
    for cn, expected in test_cases:
        result = chinese_year_to_int(cn)
        if result == expected:
            print(f"  [OK] '{cn}' -> {result}")
            passed += 1
        else:
            print(f"  [FAIL] '{cn}' -> {result} (expected {expected})")
    
    print(f"  Chinese year: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_author_parsing():
    """Test author name parsing."""
    print("\nTesting author parsing...")
    from rename_papers import parse_all_authors, clean_author_string
    
    test_cases = [
        (
            "Weihao Wang, Rufeng Zhang, Mingyu You*, Hongjun Zhou, Bin He",
            ["Wang", "Zhang", "You", "Zhou", "He"],
            "Standard author list"
        ),
        (
            "Viet Dung Nguyen *1, Quan H. Nguyen *2, Richard G. Freedman 3",
            ["Nguyen", "Nguyen", "Freedman"],
            "Authors with superscripts"
        ),
        (
            "John Smith and Jane Doe",
            ["Smith", "Doe"],
            "Authors with 'and'"
        ),
    ]
    
    passed = 0
    for text, expected_surnames, desc in test_cases:
        authors = parse_all_authors(text)
        surnames = [a['surname'] for a in authors]
        if surnames == expected_surnames:
            print(f"  [OK] {desc}: {surnames}")
            passed += 1
        else:
            print(f"  [FAIL] {desc}: {surnames} (expected {expected_surnames})")
    
    print(f"  Author parsing: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_author_formatting():
    """Test author format options."""
    print("\nTesting author formatting...")
    from rename_papers import format_authors_for_filename
    
    # Test English authors
    authors = [
        {'full_name': 'Weihao Wang', 'surname': 'Wang'},
        {'full_name': 'Rufeng Zhang', 'surname': 'Zhang'},
        {'full_name': 'Mingyu You', 'surname': 'You'},
    ]
    
    test_cases = [
        ('first_surname', 'Wang'),
        ('first_full', 'Weihao Wang'),
        ('all_surnames', 'Wang, Zhang, You'),
        ('all_full', 'Weihao Wang, Rufeng Zhang, Mingyu You'),
        ('n_surnames', 'Wang, Zhang et al.'),  # n=2
        ('n_full', 'Weihao Wang, Rufeng Zhang et al.'),  # n=2
    ]
    
    passed = 0
    for fmt, expected in test_cases:
        n = 2 if fmt.startswith('n_') else 3
        result = format_authors_for_filename(authors, fmt, n)
        if result == expected:
            print(f"  [OK] {fmt}: '{result}'")
            passed += 1
        else:
            print(f"  [FAIL] {fmt}: '{result}' (expected '{expected}')")
    
    # Test Chinese authors - should always use full name
    print("\n  Testing Chinese author formatting...")
    chinese_authors = [
        {'full_name': '张三', 'surname': '张'},
        {'full_name': '李四', 'surname': '李'},
    ]
    
    chinese_test_cases = [
        ('first_surname', '张三'),  # Should use full name, not just surname
        ('first_full', '张三'),
        ('all_surnames', '张三, 李四'),  # Should use full names
        ('all_full', '张三, 李四'),
    ]
    
    for fmt, expected in chinese_test_cases:
        result = format_authors_for_filename(chinese_authors, fmt, 3)
        if result == expected:
            print(f"  [OK] Chinese {fmt}: '{result}'")
            passed += 1
        else:
            print(f"  [FAIL] Chinese {fmt}: '{result}' (expected '{expected}')")
    
    total_tests = len(test_cases) + len(chinese_test_cases)
    print(f"  Author formatting: {passed}/{total_tests} passed")
    return passed == total_tests


def test_filename_sanitization():
    """Test filename sanitization."""
    print("\nTesting filename sanitization...")
    from rename_papers import sanitize_filename
    
    test_cases = [
        ("Normal Title", "Normal Title"),
        ("Title: With Colon", "Title With Colon"),
        ("Title/With/Slashes", "TitleWithSlashes"),
        ("Title  With   Spaces", "Title With Spaces"),
        ("Title<With>Special*Chars?", "TitleWithSpecialChars"),
    ]
    
    passed = 0
    for input_str, expected in test_cases:
        result = sanitize_filename(input_str)
        if result == expected:
            print(f"  [OK] '{input_str}' -> '{result}'")
            passed += 1
        else:
            print(f"  [FAIL] '{input_str}' -> '{result}' (expected '{expected}')")
    
    print(f"  Filename sanitization: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_pdf_processing():
    """Test PDF processing if sample files exist."""
    print("\nTesting PDF processing...")
    from pathlib import Path
    
    # Check for sample PDFs
    base_dir = Path(__file__).parent
    sample_dirs = ['AAAI_37', 'AAAI_38', 'AAAI_39']
    
    pdf_found = False
    for subdir in sample_dirs:
        subdir_path = base_dir / subdir
        if subdir_path.exists():
            pdfs = list(subdir_path.glob('*.pdf'))[:3]  # Test first 3
            if pdfs:
                pdf_found = True
                print(f"  Found {len(list(subdir_path.glob('*.pdf')))} PDFs in {subdir}")
                
                from rename_papers import parse_aaai_paper_info
                for pdf in pdfs:
                    try:
                        title, authors, year = parse_aaai_paper_info(str(pdf), subdir)
                        if title and authors:
                            print(f"    [OK] {pdf.name[:50]}...")
                            print(f"         Title: {title[:60]}...")
                            print(f"         Authors: {[a['surname'] for a in authors[:3]]}")
                            print(f"         Year: {year}")
                        else:
                            print(f"    [WARN] Could not extract info from {pdf.name[:50]}...")
                    except Exception as e:
                        print(f"    [FAIL] Error processing {pdf.name}: {e}")
    
    if not pdf_found:
        print("  [SKIP] No sample PDF files found")
    
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("AAAI Paper Renamer - Test Suite")
    print("=" * 60)
    
    all_passed = True
    
    if not test_imports():
        print("\n[FATAL] Import test failed. Cannot continue.")
        return 1
    
    all_passed &= test_year_extraction()
    all_passed &= test_chinese_year()
    all_passed &= test_author_parsing()
    all_passed &= test_author_formatting()
    all_passed &= test_filename_sanitization()
    test_pdf_processing()  # This is informational, doesn't fail the suite
    
    print("\n" + "=" * 60)
    if all_passed:
        print("All tests PASSED!")
        print("=" * 60)
        print("\nYou can now run the main script:")
        print("  python rename_papers.py --dry-run      # Preview changes")
        print("  python rename_papers.py --execute      # Apply changes")
        return 0
    else:
        print("Some tests FAILED!")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
