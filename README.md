# Chou (瞅) - Academic Paper PDF Renamer

A Python tool to automatically rename academic PDF papers to citation-style filenames by extracting title, author, and year information from the PDF content.

## Features

- Extracts title and authors from PDF first page using font size analysis
- **OCR support** for scanned PDFs (5 OCR backends available)
- Extracts publication year using 10 different strategies (supports English and Chinese)
- **Chinese name handling** - automatically uses full names for Chinese authors
- **Chinese thesis/dissertation support** - detects labeled fields like "论文题目", "作者姓名"
- Multiple author format options
- Dry-run mode for safe preview
- Handles special characters and Unicode in author names
- Logs all operations and exports results to CSV

## Requirements

- Python >= 3.10
- PyMuPDF (required)
- OCR backend (optional, for scanned PDFs)

## Installation

### From PyPI

```bash
pip install chou
```

### From Source

```bash
git clone https://github.com/cycleuser/Chou.git
cd Chou
pip install -e .
```

### With OCR Support

Choose one or more OCR backends based on your needs:

```bash
# Install with all OCR backends
pip install -e ".[ocr-surya,ocr-paddle,ocr-rapid,ocr-easy,ocr-tesseract]"

# Or install specific backends:
pip install surya-ocr          # Surya - Best accuracy, transformer-based (recommended)
pip install paddleocr paddlepaddle  # PaddleOCR - Good for Chinese
pip install rapidocr-onnxruntime    # RapidOCR - Lightweight, fast
pip install easyocr                 # EasyOCR - Easy to use
pip install pytesseract Pillow      # Tesseract - Classic OCR
```

## Quick Start

After installation, the `chou` command is available:

```bash
# Preview changes (dry-run mode, default)
chou --dir /path/to/papers --dry-run

# Actually rename files
chou --dir /path/to/papers --execute

# Show version
chou --version
```

## Usage

```bash
chou [options]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--dir DIR` | `-d` | Directory containing PDF files (default: current) |
| `--dry-run` | `-n` | Preview without renaming (default: True) |
| `--execute` | `-x` | Actually rename files |
| `--format FMT` | `-f` | Author name format (see below) |
| `--num-authors N` | `-N` | Number of authors for n_* formats (default: 3) |
| `--recursive` | `-r` | Process subdirectories recursively (default: True) |
| `--no-recursive` | | Only process the specified directory |
| `--ocr-engine` | | Specify OCR engine (default: auto-detect) |
| `--no-ocr` | | Disable OCR fallback |
| `--output FILE` | `-o` | Export results to CSV file |
| `--log-file FILE` | `-l` | Log file path |
| `--verbose` | `-v` | Verbose output |

### Author Format Options (`-f`)

| Format | Example Output |
|--------|----------------|
| `first_surname` | `Wang et al. (2023) - Title.pdf` |
| `first_full` | `Weihao Wang et al. (2023) - Title.pdf` |
| `all_surnames` | `Wang, Zhang, You (2023) - Title.pdf` |
| `all_full` | `Weihao Wang, Rufeng Zhang, Mingyu You (2023) - Title.pdf` |
| `n_surnames` | `Wang, Zhang et al. (2023) - Title.pdf` |
| `n_full` | `Weihao Wang, Rufeng Zhang et al. (2023) - Title.pdf` |

**Note:** For Chinese authors, full names are always used (e.g., `张三` instead of just `张`) since single-character surnames are not meaningful.

### Examples

```bash
# Use first author's full name
chou -d /path/to/papers -f first_full --dry-run

# Use first 2 authors' surnames
chou -d /path/to/papers -f n_surnames -N 2 --dry-run

# Process and export results
chou -d /path/to/papers --execute -o results.csv

# Use specific OCR engine
chou -d /path/to/papers --ocr-engine rapidocr --dry-run

# Disable OCR
chou -d /path/to/papers --no-ocr --dry-run
```

## OCR Support

For scanned PDFs without embedded text, the tool automatically uses OCR. Available backends (in priority order):

| Backend | Install Command | Notes |
|---------|-----------------|-------|
| Surya | `pip install surya-ocr` | Best accuracy, transformer-based |
| PaddleOCR | `pip install paddleocr paddlepaddle` | Good for Chinese |
| RapidOCR | `pip install rapidocr-onnxruntime` | Lightweight, fast |
| EasyOCR | `pip install easyocr` | Easy to use |
| Tesseract | `pip install pytesseract Pillow` | Classic OCR |

The tool automatically selects the best available backend. To disable a specific backend:

```bash
# Disable Surya OCR (e.g., on low-memory systems)
export CHOU_DISABLE_SURYA=1
chou --dry-run
```

## Year Extraction Strategies

The tool uses 10 strategies to extract publication year, ranked by confidence:

1. **Conference + year** (100): `CVPR 2023`, `NeurIPS'22`, `AAAI-23`
2. **Ordinal edition** (90): `Thirty-Seventh AAAI Conference`
3. **Copyright notice** (85): `Copyright 2023`, `(c) 2023`
4. **Publication date** (80): `Published: 2023`, `Accepted: Jan 2023`
5. **Chinese year** (78): `2023年`, `二〇二三年`
6. **arXiv ID** (75): `arXiv:2301.12345`
7. **DOI with year** (75): `10.1109/CVPR.2023.xxx`
8. **Journal volume** (70): `Vol. 35, 2023`
9. **Date pattern** (60-65): `March 2023`, `2023/03`
10. **Frequent year** (20-50): Most common year in text

## Supported Conferences

AAAI, IJCAI, NeurIPS, ICML, ICLR, CVPR, ICCV, ECCV, ACL, EMNLP, NAACL, SIGIR, KDD, WWW, CHI, USENIX, and 50+ more.

## Project Structure

```
Chou/
├── chou/                  # Main package
│   ├── core/             # Core functionality
│   │   ├── processor.py       # PDF processing
│   │   ├── ocr_extractor.py   # OCR backends
│   │   ├── author_parser.py   # Author name parsing
│   │   ├── year_parser.py     # Year extraction
│   │   └── filename_gen.py    # Filename generation
│   ├── cli/              # Command-line interface
│   └── gui/              # GUI (optional)
├── tests/                # pytest tests
├── requirements.txt      # Dependencies
├── pyproject.toml        # Package configuration
├── README.md             # This file
└── README_CN.md          # Chinese documentation
```

## GUI (Optional)

A graphical user interface is available:

```bash
pip install chou[gui]
chou-gui
```

## Development

```bash
# Install development dependencies
pip install -e ".[test]"

# Run tests
pytest

# Run with verbose output
pytest -v
```

## License

MIT License
