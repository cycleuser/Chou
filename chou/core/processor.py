"""
Main paper processing orchestrator
"""

import re
import logging
from pathlib import Path
from typing import List, Optional

from .models import Author, PaperInfo, AuthorFormat
from .extractor import (
    extract_first_page_text,
    extract_multi_page_text,
    extract_text_blocks_with_font,
)
from .year_parser import extract_year_from_text
from .author_parser import parse_all_authors, is_valid_authors_list
from .filename_gen import generate_citation_filename
from ..utils.constants import HEADER_PATTERNS, DEFAULT_YEAR

logger = logging.getLogger(__name__)


class PaperProcessor:
    """
    Main processing class for academic paper PDF renaming.
    Stateless design for use in both CLI and GUI.
    """
    
    def __init__(
        self,
        author_format: AuthorFormat = AuthorFormat.FIRST_SURNAME,
        n_authors: int = 3,
        fallback_year: int = DEFAULT_YEAR,
        ocr_engine: Optional[str] = None,
    ):
        """
        Initialize processor with configuration.
        
        Args:
            author_format: Format for author names in filename
            n_authors: Number of authors for n_* formats
            fallback_year: Year to use if extraction fails
            ocr_engine: OCR engine name (None = auto-detect, "none" = disable)
        """
        self.author_format = author_format
        self.n_authors = n_authors
        self.fallback_year = fallback_year
        self.ocr_engine = ocr_engine
    
    def process_single(self, pdf_path: Path) -> PaperInfo:
        """
        Process a single PDF file and extract metadata.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            PaperInfo with extracted data
        """
        paper = PaperInfo(file_path=pdf_path)
        
        try:
            # Try structured extraction first
            title, authors, year = self._parse_paper_structured(str(pdf_path))
            
            # Fallback if structured extraction failed
            if not title or not authors:
                title, authors, year = self._parse_paper_fallback(str(pdf_path))
            
            paper.title = title
            paper.authors = authors
            paper.year = year if year else self.fallback_year
            
            # Validate extraction
            if not paper.title or not is_valid_authors_list(paper.authors):
                paper.status = "error"
                paper.error_message = "Could not extract valid title or authors"
                return paper
            
            # Generate new filename
            paper.new_filename = generate_citation_filename(
                paper.title,
                paper.authors,
                paper.year,
                self.author_format,
                self.n_authors
            )
            paper.status = "success"
            
        except Exception as e:
            paper.status = "error"
            paper.error_message = str(e)
            logger.error(f"Error processing {pdf_path}: {e}")
        
        return paper
    
    def process_directory(
        self,
        directory: Path,
        recursive: bool = False
    ) -> List[PaperInfo]:
        """
        Process all PDFs in a directory.
        
        Args:
            directory: Directory containing PDF files
            recursive: Whether to search subdirectories
            
        Returns:
            List of PaperInfo for each PDF
        """
        results = []
        
        if recursive:
            pdf_files = list(directory.rglob('*.pdf'))
        else:
            pdf_files = list(directory.glob('*.pdf'))
        
        for pdf_path in pdf_files:
            paper = self.process_single(pdf_path)
            results.append(paper)
        
        return results
    
    def apply_renames(
        self,
        papers: List[PaperInfo],
        dry_run: bool = True
    ) -> List[PaperInfo]:
        """
        Apply renaming operations to papers.
        
        Args:
            papers: List of PaperInfo objects
            dry_run: If True, don't actually rename
            
        Returns:
            Updated list of PaperInfo with status
        """
        for paper in papers:
            if paper.status != "success" or not paper.new_filename:
                continue
            
            new_path = paper.file_path.parent / paper.new_filename
            
            # Handle duplicate names
            if new_path.exists() and new_path != paper.file_path:
                counter = 2
                while new_path.exists():
                    base_name = paper.new_filename[:-4]  # Remove .pdf
                    paper.new_filename = f"{base_name} ({counter}).pdf"
                    new_path = paper.file_path.parent / paper.new_filename
                    counter += 1
            
            if not dry_run:
                try:
                    paper.file_path.rename(new_path)
                    paper.file_path = new_path
                    logger.info(f"Renamed: {paper.original_filename} -> {paper.new_filename}")
                except Exception as e:
                    paper.status = "error"
                    paper.error_message = f"Rename failed: {e}"
                    logger.error(f"Failed to rename {paper.file_path}: {e}")
        
        return papers
    
    def update_paper_filename(self, paper: PaperInfo) -> PaperInfo:
        """
        Regenerate filename for a paper (e.g., after manual edit).
        
        Args:
            paper: PaperInfo to update
            
        Returns:
            Updated PaperInfo
        """
        if paper.title and paper.authors and paper.year:
            paper.new_filename = generate_citation_filename(
                paper.title,
                paper.authors,
                paper.year,
                self.author_format,
                self.n_authors
            )
            paper.status = "success"
        return paper
    
    def _parse_paper_structured(self, pdf_path: str):
        """
        Parse paper using font-based structured extraction.
        
        Returns:
            Tuple of (title, authors, year)
        """
        blocks = extract_text_blocks_with_font(pdf_path)
        
        if not blocks:
            return None, [], None
        
        # Get text for year extraction
        first_page_text = ' '.join([b["text"] for b in blocks])
        year = extract_year_from_text(first_page_text)
        
        # If not found on first page, search in first 3 pages
        if not year:
            multi_page_text = extract_multi_page_text(pdf_path, max_pages=3, ocr_engine=self.ocr_engine)
            if multi_page_text:
                year = extract_year_from_text(multi_page_text)
        
        # Filter header/footer content
        content_blocks = []
        for block in blocks:
            text = block["text"]
            is_header = any(re.search(pat, text, re.IGNORECASE) for pat in HEADER_PATTERNS)
            if is_header:
                continue
            if len(text) < 5:
                continue
            if '@' in text and ' ' not in text:
                continue
            content_blocks.append(block)
        
        if not content_blocks:
            return None, [], year
        
        # Sort by font size to find title
        sorted_by_font = sorted(content_blocks, key=lambda x: x["font_size"], reverse=True)
        
        title = None
        authors_text = None
        
        if sorted_by_font:
            title = sorted_by_font[0]["text"]
            title_y = sorted_by_font[0]["y"]
            title_font_size = sorted_by_font[0]["font_size"]
            
            # Combine multi-line titles
            for block in sorted_by_font[1:]:
                if abs(block["font_size"] - title_font_size) < 1 and block["y"] > title_y:
                    if block["y"] - title_y < 30:
                        title = title + " " + block["text"]
                        title_y = block["y"]
            
            # Find authors after title
            skip_keywords = ['abstract', 'introduction', 'keyword', 'department', 
                           'university', 'college', 'school', 'institute', '{', '@']
            
            for block in content_blocks:
                if block["y"] > title_y:
                    text = block["text"]
                    if any(kw in text.lower() for kw in skip_keywords):
                        continue
                    if ',' in text or '*' in text:
                        authors_text = text
                        break
                    name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+'
                    if re.search(name_pattern, text):
                        authors_text = text
                        break
        
        authors = parse_all_authors(authors_text) if authors_text else []
        
        return title, authors, year
    
    def _parse_paper_fallback(self, pdf_path: str):
        """
        Fallback parsing using simple text extraction.
        
        Returns:
            Tuple of (title, authors, year)
        """
        text = extract_first_page_text(pdf_path, ocr_engine=self.ocr_engine)
        
        if not text:
            return None, [], None
        
        year = extract_year_from_text(text)
        
        if not year:
            multi_page_text = extract_multi_page_text(pdf_path, max_pages=3, ocr_engine=self.ocr_engine)
            if multi_page_text:
                year = extract_year_from_text(multi_page_text)
        
        if not year:
            year = self.fallback_year
        
        # Try Chinese thesis/dissertation parsing first
        result = self._try_parse_chinese_thesis(text, year)
        if result:
            return result
        
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        # Extended header patterns for journal articles
        extended_patterns = HEADER_PATTERNS + [
            r'^\d+[-–]\d+$',  # Page ranges like "105216"
            r'^[A-Z]{3,}\s*$',  # All-caps short strings like "SFOSCIENC"
        ]
        
        # Filter headers
        content_lines = []
        for line in lines:
            if any(re.search(pat, line, re.IGNORECASE) for pat in extended_patterns):
                continue
            if len(line) < 5:
                continue
            content_lines.append(line)
        
        if len(content_lines) < 2:
            return None, [], year
        
        # Better title selection with scoring
        title = None
        title_idx = 0
        best_score = -1
        
        # Score each of the first 6 lines
        for i, line in enumerate(content_lines[:6]):
            score = len(line)
            # Position penalty: titles appear early
            score -= i * 15
            # Penalize lines with colons (likely metadata)
            if ':' in line:
                score -= 50
            # Penalize lines that are mostly digits
            digit_ratio = sum(1 for c in line if c.isdigit()) / max(len(line), 1)
            if digit_ratio > 0.3:
                score -= 80
            # Penalize very short lines
            if len(line) < 20:
                score -= 30
            # Penalize lines with parenthesized year/volume info
            if re.search(r'\(\d{4}\)', line):
                score -= 40
            # Penalize lines with institutional/address words
            address_words = ['department', 'university', 'college', 'school', 'institute',
                           'street', 'avenue', 'road', 'laboratory', 'lab ', 'faculty']
            if any(kw in line.lower() for kw in address_words):
                score -= 100
            # Penalize lines with commas and asterisks (likely author lines)
            if ('*' in line or '∗' in line) and ',' in line:
                score -= 60
            # Bonus for lines that look like academic titles
            lowercase_ratio = sum(1 for c in line if c.islower()) / max(len(line), 1)
            if lowercase_ratio > 0.5 and len(line) > 30:
                score += 20
            
            if score > best_score:
                best_score = score
                title = line
                title_idx = i
        
        # Find authors in lines after the title
        authors = []
        for line in content_lines[title_idx+1:title_idx+6]:
            if any(kw in line.lower() for kw in ['abstract', 'introduction', 'we ', 'this paper']):
                break
            # Skip institution/affiliation lines
            if any(kw in line.lower() for kw in ['department', 'university', 'college', 'school', 'institute']):
                continue
            # Look for name-like patterns
            if ',' in line or '*' in line or re.search(r'\b[A-Z]\.\w?\.\s*[A-Z]', line) or re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', line):
                authors = parse_all_authors(line)
                if authors:
                    break
        
        return title, authors, year
    
    def _try_parse_chinese_thesis(self, text: str, year: int):
        """
        Try to parse text as a Chinese thesis/dissertation with labeled fields.
        
        Returns:
            Tuple of (title, authors, year) if successful, None otherwise
        """
        # Look for explicit title label: 论文题目, 题目, 题 目
        title_match = re.search(r'(?:论文题目|题\s*目)[：:\s]*(.+)', text)
        if not title_match:
            return None
        
        title = title_match.group(1).strip()
        # Clean up: take just the first line if multi-line
        title = re.split(r'\n', title)[0].strip()
        if not title:
            return None
        
        # Look for author label: 作者姓名, 作者, 姓名
        author_match = re.search(r'(?:作者姓名|作\s*者)[：:\s]*(.+)', text)
        authors = []
        if author_match:
            author_str = author_match.group(1).strip().split('\n')[0].strip()
            # Chinese names: 2-4 CJK characters
            cn_names = re.findall(r'[\u4e00-\u9fff]{2,4}', author_str)
            if cn_names:
                for name in cn_names:
                    authors.append(Author(full_name=name, surname=name[0]))
        
        return title, authors, year
