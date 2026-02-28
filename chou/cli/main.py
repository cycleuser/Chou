"""
Chou CLI - Command Line Interface
"""

import sys
import argparse
import logging
from pathlib import Path

from ..__version__ import __version__, __app_name__, __app_name_cn__
from ..core.models import AuthorFormat
from ..core.processor import PaperProcessor
from ..core.ocr_extractor import get_available_engines


def setup_logging(log_file: str = None, verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO
    handlers = [logging.StreamHandler()]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description=f'{__app_name__} ({__app_name_cn__}) - Academic Paper PDF Renaming Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=get_format_help()
    )
    
    parser.add_argument(
        '--version', '-V',
        action='version',
        version=f'{__app_name__} ({__app_name_cn__}) {__version__}'
    )
    
    parser.add_argument(
        '--dir', '-d',
        type=Path,
        default=Path('.'),
        help='Directory containing PDF files (default: current directory)'
    )
    
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        default=True,
        help='Process subdirectories recursively (default: True)'
    )
    
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Only process the specified directory, not subdirectories'
    )
    
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        default=True,
        help='Preview changes without renaming (default: True)'
    )
    
    parser.add_argument(
        '--execute', '-x',
        action='store_true',
        help='Actually rename files (disables dry-run)'
    )
    
    parser.add_argument(
        '--format', '-f',
        type=str,
        choices=[f.value for f in AuthorFormat],
        default=AuthorFormat.FIRST_SURNAME.value,
        help='Author name format (default: first_surname)'
    )
    
    parser.add_argument(
        '--num-authors', '-N',
        type=int,
        default=3,
        help='Number of authors for n_surnames/n_full formats (default: 3)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Export results to CSV file'
    )
    
    parser.add_argument(
        '--log-file', '-l',
        type=str,
        help='Log file path'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    # OCR options
    ocr_engines = get_available_engines()
    parser.add_argument(
        '--ocr-engine',
        type=str,
        default=None,
        help=f'OCR engine to use (available: {", ".join(ocr_engines) if ocr_engines else "none installed"}). '
             f'Default: auto-detect best available.'
    )
    
    parser.add_argument(
        '--no-ocr',
        action='store_true',
        help='Disable OCR fallback for scanned PDFs'
    )
    
    # Device selection for OCR
    device_group = parser.add_mutually_exclusive_group()
    device_group.add_argument(
        '--cpu',
        action='store_true',
        help='Force OCR to run on CPU only'
    )
    device_group.add_argument(
        '--gpu',
        action='store_true',
        help='Force OCR to run on GPU (falls back to CPU if unavailable or out of memory)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_file, args.verbose)
    logger = logging.getLogger(__name__)
    
    # Determine dry_run mode
    dry_run = not args.execute
    
    # Show configuration
    author_format = AuthorFormat(args.format)
    logger.info(f"{__app_name__} ({__app_name_cn__}) v{__version__}")
    logger.info(f"Author format: {args.format} - {AuthorFormat.get_description(author_format)}")
    
    if author_format in [AuthorFormat.N_SURNAMES, AuthorFormat.N_FULL]:
        logger.info(f"Number of authors: {args.num_authors}")
    
    if dry_run:
        logger.info("DRY RUN MODE - No files will be renamed")
        logger.info("Use --execute or -x flag to actually rename files")
    else:
        logger.info("EXECUTE MODE - Files will be renamed!")
        try:
            response = input("Are you sure you want to rename files? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("Aborted by user")
                return 0
        except (EOFError, KeyboardInterrupt):
            logger.info("\nAborted")
            return 0
    
    # Check directory
    if not args.dir.exists():
        logger.error(f"Directory not found: {args.dir}")
        return 1
    
    if not args.dir.is_dir():
        logger.error(f"Not a directory: {args.dir}")
        return 1
    
    # Determine recursive mode
    recursive = not args.no_recursive
    
    logger.info(f"Processing directory: {args.dir.resolve()}")
    if recursive:
        logger.info("Recursive mode: scanning all subdirectories")
    
    # Determine OCR engine
    ocr_engine_name = "none" if args.no_ocr else args.ocr_engine
    if ocr_engine_name != "none":
        available = get_available_engines()
        if available:
            engine_display = ocr_engine_name if ocr_engine_name else available[0]
            logger.info(f"OCR engine: {engine_display} (available: {', '.join(available)})")
        else:
            logger.info("OCR: no engines installed (scanned PDFs will be skipped)")
    else:
        logger.info("OCR: disabled")
    
    # Determine device preference
    if args.cpu:
        device = "cpu"
    elif args.gpu:
        device = "gpu"
    else:
        device = None  # auto: try GPU first, fall back to CPU
    
    if device and ocr_engine_name != "none":
        logger.info(f"OCR device: {device}")
    
    # Process papers
    processor = PaperProcessor(
        author_format=author_format,
        n_authors=args.num_authors,
        ocr_engine=ocr_engine_name,
        device=device,
    )
    
    papers = processor.process_directory(args.dir, recursive=recursive)
    
    if not papers:
        logger.warning("No PDF files found")
        return 0
    
    # Show results
    success_count = sum(1 for p in papers if p.status == "success")
    error_count = sum(1 for p in papers if p.status == "error")
    
    for paper in papers:
        if paper.status == "success":
            if dry_run:
                logger.info(f"[DRY RUN] Would rename:\n  FROM: {paper.original_filename}\n  TO:   {paper.new_filename}")
            else:
                pass  # Will be logged during apply_renames
        else:
            logger.warning(f"Could not process: {paper.original_filename} - {paper.error_message}")
    
    # Apply renames
    if not dry_run:
        papers = processor.apply_renames(papers, dry_run=False)
    
    # Export results
    if args.output:
        export_results_csv(papers, args.output)
        logger.info(f"Results saved to: {args.output}")
    
    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY:")
    logger.info(f"  Total:   {len(papers)}")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Errors:  {error_count}")
    logger.info("=" * 60)
    
    return 0 if error_count == 0 else 1


def get_format_help() -> str:
    """Generate format options help text"""
    lines = ["\nAuthor format options:"]
    for fmt in AuthorFormat:
        lines.append(f"  {fmt.value}: {AuthorFormat.get_description(fmt)}")
    return '\n'.join(lines)


def export_results_csv(papers, output_path: Path):
    """Export results to CSV file"""
    import csv
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['original', 'new', 'title', 'authors', 'year', 'status', 'error']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for paper in papers:
            writer.writerow({
                'original': paper.original_filename,
                'new': paper.new_filename or '',
                'title': paper.title or '',
                'authors': ', '.join(a.surname for a in paper.authors),
                'year': paper.year or '',
                'status': paper.status,
                'error': paper.error_message or ''
            })


if __name__ == '__main__':
    sys.exit(main())
