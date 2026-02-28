import fitz
import os
from pathlib import Path

test_dir = Path(r"z:\Home\Documents\GitHub\Chou\test")
print(f"test_dir exists: {test_dir.exists()}")
for pdf in sorted(test_dir.glob("*.pdf")):
    print(f"\n--- {pdf.name} ---")
    print(f"  size: {pdf.stat().st_size} bytes")
    try:
        doc = fitz.open(str(pdf))
        print(f"  pages: {len(doc)}")
        if len(doc) > 0:
            text = doc[0].get_text()
            print(f"  first page text length: {len(text)}")
            print(f"  first 200 chars: {repr(text[:200])}")
        doc.close()
    except Exception as e:
        print(f"  ERROR: {e}")
