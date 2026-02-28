import sys
checks = {
    "pytesseract": False,
    "easyocr": False,
    "paddleocr": False,
    "rapidocr_onnxruntime": False,
}
for mod in checks:
    try:
        __import__(mod)
        checks[mod] = True
    except ImportError:
        pass
for k, v in checks.items():
    print(f"{k}: {'OK' if v else 'NOT FOUND'}")

# Check PyMuPDF OCR support
import fitz
print(f"PyMuPDF version: {fitz.__doc__.split()[1]}")
print(f"PyMuPDF has tessocr: {hasattr(fitz, 'TOOLS')}")
try:
    val = fitz.TOOLS.store_shrink(100)
    print(f"TOOLS accessible: True")
except:
    print(f"TOOLS accessible: False")
