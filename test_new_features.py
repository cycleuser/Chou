"""
Test script for new Chou features:
- Journal name extraction
- Title abbreviation
"""

from chou.core.filename_gen import abbreviate_title, generate_citation_filename
from chou.core.models import Author, AuthorFormat


def test_abbreviate_title():
    """Test title abbreviation function"""
    print("Testing title abbreviation...")
    
    # Short title - no change
    short = "Machine Learning"
    result = abbreviate_title(short, max_length=50)
    assert result == short, f"Short title should not be abbreviated: {result}"
    print(f"  ✓ Short title unchanged: '{result}'")
    
    # Long title - should abbreviate
    long_title = "A Comprehensive Study on Deep Learning Applications in Natural Language Processing and Computer Vision"
    result = abbreviate_title(long_title, max_length=50)
    assert len(result) <= 53, f"Abbreviated title too long: {len(result)} chars"
    assert result.endswith('...'), f"Should end with ellipsis: {result}"
    print(f"  ✓ Long title abbreviated: '{result}'")
    
    # Title with colon - should break at colon
    titled_colon = "Deep Learning: A Comprehensive Survey of Methods and Applications in Various Domains"
    result = abbreviate_title(titled_colon, max_length=50)
    print(f"  ✓ Title with colon: '{result}'")
    
    print("Title abbreviation tests passed!\n")


def test_generate_filename_with_options():
    """Test filename generation with new options"""
    print("Testing filename generation with new features...")
    
    authors = [
        Author(full_name="John Smith", surname="Smith"),
        Author(full_name="Jane Doe", surname="Doe"),
    ]
    year = 2024
    title = "A Very Long Title That Should Be Abbreviated When Using The Abbreviation Feature"
    journal = "Nature Communications"
    
    # Standard format
    result = generate_citation_filename(
        title=title,
        authors=authors,
        year=year,
        author_format=AuthorFormat.FIRST_SURNAME,
    )
    print(f"  Standard: {result}")
    
    # With title abbreviation
    result = generate_citation_filename(
        title=title,
        authors=authors,
        year=year,
        author_format=AuthorFormat.FIRST_SURNAME,
        abbreviate_titles=True,
        max_title_length=40,
    )
    print(f"  Abbreviated title: {result}")
    assert '...' in result, "Should contain ellipsis"
    
    # With journal
    result = generate_citation_filename(
        title=title,
        authors=authors,
        year=year,
        author_format=AuthorFormat.FIRST_SURNAME,
        include_journal=True,
        journal=journal,
    )
    print(f"  With journal: {result}")
    assert 'Nature' in result, "Should include journal name"
    
    # With both journal and abbreviated title
    result = generate_citation_filename(
        title=title,
        authors=authors,
        year=year,
        author_format=AuthorFormat.FIRST_FULL,
        abbreviate_titles=True,
        max_title_length=30,
        include_journal=True,
        journal=journal,
    )
    print(f"  Journal + abbreviated: {result}")
    
    print("Filename generation tests passed!\n")


def test_paper_info_with_journal():
    """Test PaperInfo model with journal field"""
    print("Testing PaperInfo model with journal field...")
    
    from chou.core.models import PaperInfo
    from pathlib import Path
    
    paper = PaperInfo(
        file_path=Path("/test/paper.pdf"),
        title="Test Paper",
        authors=[Author(full_name="Test User", surname="User")],
        year=2024,
        journal="Test Journal"
    )
    
    assert paper.journal == "Test Journal", "Journal should be stored"
    print(f"  ✓ Journal stored: {paper.journal}")
    print("PaperInfo tests passed!\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing New Chou Features")
    print("=" * 60 + "\n")
    
    test_abbreviate_title()
    test_generate_filename_with_options()
    test_paper_info_with_journal()
    
    print("=" * 60)
    print("All tests passed successfully!")
    print("=" * 60)
