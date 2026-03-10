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
        device: Optional[str] = None,
        abbreviate_titles: bool = False,
        max_title_length: int = 50,
        include_journal: bool = False,
        abbreviate_journal: bool = False,
        max_journal_length: int = 30,
    ):
        """
        Initialize processor with configuration.
        
        Args:
            author_format: Format for author names in filename
            n_authors: Number of authors for n_* formats
            fallback_year: Year to use if extraction fails
            ocr_engine: OCR engine name (None = auto-detect, "none" = disable)
            device: Device preference for OCR: "cpu", "gpu", or None (auto: try GPU, fall back to CPU)
            abbreviate_titles: Whether to abbreviate long titles
            max_title_length: Maximum title length before abbreviation
            include_journal: Whether to include journal name in filename
            abbreviate_journal: Whether to abbreviate long journal names
            max_journal_length: Maximum journal name length before abbreviation
        """
        self.author_format = author_format
        self.n_authors = n_authors
        self.fallback_year = fallback_year
        self.ocr_engine = ocr_engine
        self.device = device
        self.abbreviate_titles = abbreviate_titles
        self.max_title_length = max_title_length
        self.include_journal = include_journal
        self.abbreviate_journal = abbreviate_journal
        self.max_journal_length = max_journal_length
    
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
            title, authors, year, journal = self._parse_paper_structured(str(pdf_path))
            
            # Fallback if structured extraction failed
            if not title or not authors:
                title, authors, year, journal_fb = self._parse_paper_fallback(str(pdf_path))
                if not journal:
                    journal = journal_fb
            
            paper.title = title
            paper.authors = authors
            paper.year = year if year else self.fallback_year
            paper.journal = journal
            
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
                self.n_authors,
                abbreviate_titles=self.abbreviate_titles,
                max_title_length=self.max_title_length,
                include_journal=self.include_journal,
                journal=paper.journal,
                abbreviate_journal=self.abbreviate_journal,
                max_journal_length=self.max_journal_length,
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
                self.n_authors,
                abbreviate_titles=self.abbreviate_titles,
                max_title_length=self.max_title_length,
                include_journal=self.include_journal,
                journal=paper.journal,
                abbreviate_journal=self.abbreviate_journal,
                max_journal_length=self.max_journal_length,
            )
            paper.status = "success"
        return paper
    
    def _parse_paper_structured(self, pdf_path: str):
        """
        Parse paper using font-based structured extraction.
        
        Returns:
            Tuple of (title, authors, year, journal)
        """
        blocks = extract_text_blocks_with_font(pdf_path)
        
        if not blocks:
            return None, [], None, None
        
        # Get text for year extraction
        first_page_text = ' '.join([b["text"] for b in blocks])
        year = extract_year_from_text(first_page_text)
        
        # If not found on first page, search in first 3 pages
        if not year:
            multi_page_text = extract_multi_page_text(pdf_path, max_pages=3, ocr_engine=self.ocr_engine, device=self.device)
            if multi_page_text:
                year = extract_year_from_text(multi_page_text)
        
        # Detect header zone at top of page using structural journal elements
        # (not article-type labels like "Research Paper" which sit close to the title)
        journal_zone_patterns = [
            r'ScienceDirect', r'Elsevier', r'Springer',
            r'journal\s+homepage', r'Contents\s+lists?\s+available',
            r'HOSTED\s+BY', r'www\.', r'https?://',
        ]
        header_zone_y = 0
        for block in blocks:
            text = block["text"]
            is_journal = any(re.search(pat, text, re.IGNORECASE) for pat in journal_zone_patterns)
            if is_journal and block["y"] < 200:
                header_zone_y = max(header_zone_y, block["y"])
        if header_zone_y > 0:
            header_zone_y += 30  # margin below last journal header block
        
        # Extract journal name from header zone blocks
        journal = self._extract_journal_from_blocks(blocks, header_zone_y)
        
        # Filter header/footer content
        content_blocks = []
        for block in blocks:
            text = block["text"]
            is_header = any(re.search(pat, text, re.IGNORECASE) for pat in HEADER_PATTERNS)
            if is_header:
                continue
            # Skip blocks in header zone (journal name, article type labels)
            if header_zone_y > 0 and block["y"] <= header_zone_y:
                continue
            if len(text) < 5:
                continue
            if '@' in text and ' ' not in text:
                continue
            content_blocks.append(block)
        
        if not content_blocks:
            return None, [], year, journal
        
        # Sort by font size to find title
        sorted_by_font = sorted(content_blocks, key=lambda x: x["font_size"], reverse=True)
        
        title = None
        authors_text = None
        
        if sorted_by_font:
            title = sorted_by_font[0]["text"]
            title_y = sorted_by_font[0]["y"]
            title_font_size = sorted_by_font[0]["font_size"]
            
            # Combine multi-line titles (same font size, close y positions)
            # Collect all same-font blocks and sort by y to build the title in order
            title_blocks = [sorted_by_font[0]]
            for block in sorted_by_font[1:]:
                if abs(block["font_size"] - title_font_size) < 1:
                    if abs(block["y"] - title_y) < 30 or any(
                        abs(block["y"] - tb["y"]) < 30 for tb in title_blocks
                    ):
                        title_blocks.append(block)
            title_blocks.sort(key=lambda x: x["y"])
            title = " ".join(b["text"] for b in title_blocks)
            title_y = title_blocks[-1]["y"]
            
            # Find authors after title, sorted by proximity to title
            skip_keywords = ['abstract', 'introduction', 'keyword', 'department', 
                           'university', 'college', 'school', 'institute', '{', '@']
            
            candidate_blocks = sorted(
                [b for b in content_blocks if b["y"] > title_y],
                key=lambda x: x["y"]
            )
            
            for block in candidate_blocks:
                if block["y"] - title_y > 150:
                    break
                text = block["text"]
                if any(kw in text.lower() for kw in skip_keywords):
                    continue
                if ',' in text or '\uff0c' in text or '*' in text:
                    authors_text = text
                    break
                name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+'
                if re.search(name_pattern, text):
                    authors_text = text
                    break
        
        authors = parse_all_authors(authors_text) if authors_text else []
        
        return title, authors, year, journal
    
    def _parse_paper_fallback(self, pdf_path: str):
        """
        Fallback parsing using simple text extraction.
        
        Returns:
            Tuple of (title, authors, year, journal)
        """
        text = extract_first_page_text(pdf_path, ocr_engine=self.ocr_engine, device=self.device)
        
        if not text:
            return None, [], None, None
        
        # Strip HTML tags from OCR output (Surya produces <sup>, <b>, <br> etc.)
        text = self._strip_ocr_html(text)
        
        year = extract_year_from_text(text)
        
        if not year:
            multi_page_text = extract_multi_page_text(pdf_path, max_pages=3, ocr_engine=self.ocr_engine, device=self.device)
            if multi_page_text:
                year = extract_year_from_text(multi_page_text)
        
        if not year:
            year = self.fallback_year
        
        # Try Chinese thesis/dissertation parsing first
        result = self._try_parse_chinese_thesis(text, year)
        if result:
            return result
        
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        # Extract journal name from early lines before filtering
        journal = self._extract_journal_from_lines(lines)
        
        # Extended header patterns for journal articles
        extended_patterns = HEADER_PATTERNS + [
            r'^\d+[-–]\d+$',  # Page ranges like "105216"
            r'^[A-Z]{3,}\s*$',  # All-caps short strings like "SFOSCIENC"
            r'\(\d{4}\)\s*\d+[-–—]\d+',  # Journal citation: (2019) 1437-1447
            r'^第\s*\d+\s*卷',  # Chinese volume: 第34卷
            r'^Vol\.\s*\d+',  # Volume: Vol. 34
            r'^DOI\s*:',  # DOI line
            r'文章编号',  # Chinese article number
            r'中图分类号',  # Chinese CLC code
            r'文献标志码',  # Chinese document code
            r'开放科学',  # Open science identifier
            r'^\d{4}\s*年\s*\d+\s*月',  # Chinese date: 2025年4月
            r'^[A-Z][a-z]+\.\s*\d{4}\s*$',  # English date: Apr. 2025
            r'^No\.\s*\d+',  # Issue number
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
        best_score = float('-inf')
        
        # Score each of the first 10 lines (OCR text may have many header lines)
        for i, line in enumerate(content_lines[:10]):
            score = len(line)
            # Position penalty: titles appear early (gentler for OCR text)
            score -= i * 10
            # Penalize lines with colons (likely metadata) — but mild for long lines
            # or lines where colon appears after a short prefix (subtitle pattern)
            if ':' in line or '\uff1a' in line:
                colon_pos = line.find(':')
                if colon_pos < 0:
                    colon_pos = line.find('\uff1a')
                rest_after_colon = line[colon_pos+1:].strip() if colon_pos >= 0 else ''
                if len(rest_after_colon) > 15:
                    # Colon with long content after — likely a title with subtitle
                    score -= 5
                elif len(line) < 40:
                    score -= 50
                else:
                    score -= 15
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
            # Penalize all-uppercase lines (likely journal name or section header)
            if line == line.upper() and len(line) > 5:
                score -= 60
            # Penalize journal-name-like lines (short, title case, no verbs)
            if len(line) < 30 and re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+){0,3}$', line):
                score -= 40
            # Bonus for lines that look like academic titles
            lowercase_ratio = sum(1 for c in line if c.islower()) / max(len(line), 1)
            if lowercase_ratio > 0.5 and len(line) > 30:
                score += 20
            # Bonus for CJK-heavy lines that are long (likely Chinese titles)
            cjk_count = sum(1 for c in line if '\u4e00' <= c <= '\u9fff')
            if cjk_count > 5 and len(line) > 15:
                score += 15
            
            if score > best_score:
                best_score = score
                title = line
                title_idx = i
        
        # Combine multi-line titles: check if next line is a continuation
        if title and title_idx + 1 < len(content_lines):
            next_line = content_lines[title_idx + 1]
            # Next line is likely a continuation if:
            # - It's not an author line (no commas with names, no asterisks)
            # - It doesn't start with a keyword (abstract, etc.)
            # - It's relatively short (< title) and doesn't look like metadata
            is_author_line = (',' in next_line or '\uff0c' in next_line) and (
                '*' in next_line or re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', next_line))
            is_keyword = any(kw in next_line.lower() for kw in [
                'abstract', 'introduction', '\u6458'])
            is_metadata = ':' in next_line and len(next_line) < 30
            has_cjk_names = bool(re.match(r'^[\u4e00-\u9fff]{2,4}[0-9,\uff0c]', next_line))
            if not is_author_line and not is_keyword and not is_metadata and not has_cjk_names:
                # Looks like a title continuation
                if len(next_line) < len(title) and len(next_line) > 5:
                    title = title + " " + next_line
                    title_idx += 1
        
        # Find authors in lines after the title
        authors = []
        for line in content_lines[title_idx+1:title_idx+6]:
            if any(kw in line.lower() for kw in ['abstract', 'introduction', 'we ', 'this paper']):
                break
            if '\u6458' in line:  # 摘 (abstract in Chinese)
                break
            if '\u5173\u952e\u8bcd' in line:  # 关键词 (keywords in Chinese)
                break
            # Skip institution/affiliation lines
            if any(kw in line.lower() for kw in ['department', 'university', 'college', 'school', 'institute']):
                continue
            # Look for name-like patterns
            if ',' in line or '\uff0c' in line or '*' in line or re.search(r'\b[A-Z]\.\w?\.\s*[A-Z]', line) or re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', line):
                authors = parse_all_authors(line)
                if authors:
                    break
        
        return title, authors, year, journal
    
    @staticmethod
    def _extract_journal_from_blocks(blocks, header_zone_y) -> Optional[str]:
        """
        Extract journal name from blocks within the header zone of a PDF page.
        
        Looks at blocks above the header_zone_y threshold and filters out
        publisher names, URLs, and other non-journal text.
        
        Returns:
            Journal name string or None
        """
        if header_zone_y <= 0:
            return None
        
        # Patterns to skip (publishers, URLs, generic labels, institutions)
        skip_patterns = [
            r'ScienceDirect', r'Elsevier', r'Springer', r'Wiley',
            r'Taylor\s*&\s*Francis', r'IEEE', r'ACM',
            r'journal\s+homepage', r'Contents\s+lists?\s+available',
            r'HOSTED\s+BY', r'www\.', r'https?://',
            r'Check\s+for', r'updates?',
            r'Available\s+online', r'Accepted\s+\d',
            r'Received\s+\d', r'Published\s+\d',
            r'^\s*Research\s+(Paper|Article)\s*$',
            r'^\s*(Review|Original|Research)\s+(Paper|Article)\s*$',
            r'^\s*(Short|Brief)\s+(Communication|Report)\s*$',
            r'ARTICLE\s+INFO', r'Keywords?\s*:',
            r'^\s*\d+\s*$',  # bare numbers
            r'^\s*$',
            # Institution/affiliation patterns
            r'\bUniversity\b', r'\bCollege\b', r'\bInstitute\b',
            r'\bSchool\s+of\b', r'\bDepartment\b', r'\bFaculty\b',
            r'\bLaboratory\b', r'\bCenter\b', r'\bCentre\b',
            r'\b大学\b', r'\b学院\b', r'\b研究所\b', r'\b实验室\b',
        ]
        
        candidates = []
        for block in blocks:
            if block["y"] > header_zone_y:
                continue
            text = block["text"].strip()
            if len(text) < 3:
                continue
            # Skip blocks matching publisher/URL/label patterns
            if any(re.search(pat, text, re.IGNORECASE) for pat in skip_patterns):
                continue
            # Skip blocks that are all digits or very short single words
            if re.match(r'^[\d\s.]+$', text):
                continue
            candidates.append(text)
        
        if not candidates:
            return None
        
        # Pick the best candidate: prefer longer, more journal-like text
        best = None
        for c in candidates:
            # Clean trailing volume/issue/page info
            # Matches patterns like: "10 (2019) 1437-1447", "10 (2019) 1437e1447"
            cleaned = re.sub(r'\s*\d+\s*\(\d{4}\)\s*\d+[-–eE]?\d*\s*$', '', c).strip()
            cleaned = re.sub(r'\s*Volume\s+\d+.*$', '', cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r'\s*Vol\.\s*\d+.*$', '', cleaned, flags=re.IGNORECASE).strip()
            # Clean trailing bare volume numbers: "Journal Name 123"
            cleaned = re.sub(r'\s+\d{1,4}\s*$', '', cleaned).strip()
            if len(cleaned) < 3:
                continue
            if best is None or len(cleaned) > len(best):
                best = cleaned
        
        return best
    
    @staticmethod
    def _extract_journal_from_lines(lines) -> Optional[str]:
        """
        Extract journal name from the first few lines of plain text.
        
        Looks for journal-like patterns in the header lines of a paper.
        
        Returns:
            Journal name string or None
        """
        # Patterns that indicate a line contains a journal name
        journal_indicators = [
            r'Journal\s+of\b', r'Transactions\s+on\b',
            r'Proceedings\s+of\b', r'Annals\s+of\b',
            r'Reviews?\s+of\b', r'Letters?\s+in\b',
            r'Advances\s+in\b', r'Communications\s+in\b',
            r'Archives?\s+of\b', r'Bulletin\s+of\b',
        ]
        # Chinese journal indicators
        cn_journal_indicators = [
            r'学报$', r'杂志$', r'期刊$', r'通报$', r'研究$',
            r'科学$', r'工程$', r'技术$', r'地质$', r'地球$',
        ]
        
        # Only scan first 10 lines (journal name is near the top)
        for line in lines[:10]:
            line = line.strip()
            if len(line) < 3 or len(line) > 120:
                continue
            # Skip lines that are clearly not journal names
            if re.search(r'https?://', line) or re.search(r'www\.', line):
                continue
            if re.search(r'@', line):
                continue
            
            # Check English journal indicators
            for pat in journal_indicators:
                if re.search(pat, line, re.IGNORECASE):
                    # Clean volume/page info from end
                    cleaned = re.sub(r'\s*\d+\s*\(\d{4}\).*$', '', line).strip()
                    cleaned = re.sub(r'\s*,\s*Volume\s+\d+.*$', '', cleaned, flags=re.IGNORECASE).strip()
                    if len(cleaned) >= 5:
                        return cleaned
            
            # Check Chinese journal indicators
            for pat in cn_journal_indicators:
                if re.search(pat, line):
                    # Clean trailing issue/volume info
                    cleaned = re.sub(r'\s*第?\s*\d+\s*卷.*$', '', line).strip()
                    cleaned = re.sub(r'\s*\d{4}\s*年.*$', '', cleaned).strip()
                    cleaned = re.sub(r'\s*,\s*\d+.*$', '', cleaned).strip()
                    if len(cleaned) >= 2:
                        return cleaned
        
        return None

    @staticmethod
    def _strip_ocr_html(text: str) -> str:
        """Strip HTML tags commonly produced by OCR engines like Surya."""
        # Remove <sup>...</sup> entirely (footnote markers)
        text = re.sub(r'<sup>[^<]*</sup>', '', text)
        # Remove <sub>...</sub> entirely
        text = re.sub(r'<sub>[^<]*</sub>', '', text)
        # Replace <br> / <br/> with space
        text = re.sub(r'<br\s*/?>', ' ', text)
        # Strip remaining tags but keep content (e.g., <b>text</b> -> text)
        text = re.sub(r'<[^>]+>', '', text)
        # Collapse multiple spaces
        text = re.sub(r'  +', ' ', text)
        return text
    
    def _try_parse_chinese_thesis(self, text: str, year: int):
        """
        Try to parse text as a Chinese thesis/dissertation with labeled fields.
        
        Returns:
            Tuple of (title, authors, year, journal) if successful, None otherwise
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
        
        return title, authors, year, None