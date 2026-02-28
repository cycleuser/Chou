"""
Multi-backend OCR extraction for scanned PDFs.

Supports 5 OCR engines (in priority order):
1. Surya      — transformer-based, multilingual, high accuracy
2. PaddleOCR  — best Chinese accuracy
3. RapidOCR   — lightweight ONNX-based
4. EasyOCR    — PyTorch-based, good all-round
5. Tesseract  — classic, requires system binary

All engines are optional. The module degrades gracefully when none are installed.
"""

import io
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger(__name__)

# Minimum text length to consider extraction successful
OCR_MIN_TEXT_LENGTH = 50
OCR_DEFAULT_DPI = 250
OCR_DEFAULT_MAX_PAGES = 3

# Priority order for auto-detection
ENGINE_PRIORITY = ["surya", "paddleocr", "rapidocr", "easyocr", "tesseract"]

# Module-level engine cache: (engine_name, device) -> instance
_engine_cache: dict = {}


def _is_cuda_oom(exc: Exception) -> bool:
    """Check if an exception is a CUDA out-of-memory error."""
    msg = str(exc).lower()
    return any(kw in msg for kw in [
        "cuda out of memory",
        "out of memory",
        "cublas",
        "cudnn",
        "cuda error",
        "gpu memory",
    ])


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class OcrEngine(ABC):
    """Abstract base for OCR engines."""

    name: str = "base"

    @abstractmethod
    def ocr_image(self, image_bytes: bytes) -> str:
        """Run OCR on a PNG image and return extracted text."""
        ...

    @staticmethod
    @abstractmethod
    def is_available() -> bool:
        """Check if this engine's dependencies are installed."""
        ...


# ---------------------------------------------------------------------------
# Surya OCR engine
# ---------------------------------------------------------------------------

class SuryaOcrEngine(OcrEngine):
    name = "surya"

    def __init__(self, device: Optional[str] = None):
        import torch
        from surya.foundation import FoundationPredictor  # noqa
        from surya.recognition import RecognitionPredictor  # noqa
        from surya.detection import DetectionPredictor  # noqa

        self._device = device  # "cpu", "gpu", or None (auto)

        # Resolve actual device
        if device == "cpu":
            use_device = "cpu"
        elif device == "gpu":
            if not torch.cuda.is_available():
                logger.warning("GPU requested but CUDA not available, falling back to CPU")
                use_device = "cpu"
            else:
                use_device = "cuda"
        else:
            use_device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(f"Initializing Surya OCR engine on {use_device} (may download models on first run)...")
        try:
            foundation = FoundationPredictor(device=use_device)
            self._recognition = RecognitionPredictor(foundation)
            self._detection = DetectionPredictor(device=use_device)
        except (RuntimeError, Exception) as e:
            if _is_cuda_oom(e) and use_device != "cpu":
                logger.warning(f"GPU memory insufficient for Surya, retrying on CPU: {e}")
                foundation = FoundationPredictor(device="cpu")
                self._recognition = RecognitionPredictor(foundation)
                self._detection = DetectionPredictor(device="cpu")
            else:
                raise

    @staticmethod
    def is_available() -> bool:
        try:
            from surya.foundation import FoundationPredictor  # noqa
            from surya.recognition import RecognitionPredictor  # noqa
            from surya.detection import DetectionPredictor  # noqa
        except ImportError:
            return False
        # Skip surya if explicitly disabled via environment variable
        import os
        if os.environ.get("CHOU_DISABLE_SURYA", "").lower() in ("1", "true", "yes"):
            return False
        return True

    def ocr_image(self, image_bytes: bytes) -> str:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        try:
            predictions = self._recognition(
                [img], det_predictor=self._detection
            )
        except (RuntimeError, Exception) as e:
            if _is_cuda_oom(e):
                logger.warning("GPU OOM during Surya OCR inference, retrying on CPU")
                import torch
                torch.cuda.empty_cache()
                from surya.foundation import FoundationPredictor
                from surya.detection import DetectionPredictor
                foundation = FoundationPredictor(device="cpu")
                self._recognition = self._recognition.__class__(foundation)
                self._detection = DetectionPredictor(device="cpu")
                predictions = self._recognition(
                    [img], det_predictor=self._detection
                )
            else:
                raise
        lines = []
        for page_pred in predictions:
            for text_line in page_pred.text_lines:
                if text_line.text and text_line.text.strip():
                    lines.append(text_line.text.strip())
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# PaddleOCR engine
# ---------------------------------------------------------------------------

class PaddleOcrEngine(OcrEngine):
    name = "paddleocr"

    def __init__(self, device: Optional[str] = None):
        from paddleocr import PaddleOCR  # noqa

        self._device = device
        use_gpu = self._resolve_use_gpu(device)
        logger.info(f"Initializing PaddleOCR engine (use_gpu={use_gpu})...")
        try:
            self._reader = PaddleOCR(use_textline_orientation=True, lang="ch", device="gpu" if use_gpu else "cpu")
        except (RuntimeError, Exception) as e:
            if _is_cuda_oom(e) and use_gpu:
                logger.warning(f"GPU memory insufficient for PaddleOCR, retrying on CPU: {e}")
                self._reader = PaddleOCR(use_textline_orientation=True, lang="ch", device="cpu")
            else:
                raise

    @staticmethod
    def _resolve_use_gpu(device: Optional[str]) -> bool:
        if device == "cpu":
            return False
        if device == "gpu":
            return True
        # Auto: try GPU
        try:
            import paddle
            return paddle.device.is_compiled_with_cuda()
        except Exception:
            return False

    @staticmethod
    def is_available() -> bool:
        try:
            from paddleocr import PaddleOCR  # noqa
            return True
        except ImportError:
            return False

    def ocr_image(self, image_bytes: bytes) -> str:
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)
        try:
            results = self._reader.predict(img_array)
        except (RuntimeError, Exception) as e:
            if _is_cuda_oom(e):
                logger.warning("GPU OOM during PaddleOCR inference, reinitializing on CPU")
                from paddleocr import PaddleOCR
                self._reader = PaddleOCR(use_textline_orientation=True, lang="ch", device="cpu")
                results = self._reader.predict(img_array)
            else:
                raise
        lines = []
        for res in results:
            if hasattr(res, 'rec_texts') and res.rec_texts:
                lines.extend(res.rec_texts)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# RapidOCR engine
# ---------------------------------------------------------------------------

class RapidOcrEngine(OcrEngine):
    name = "rapidocr"

    def __init__(self, device: Optional[str] = None):
        from rapidocr_onnxruntime import RapidOCR  # noqa
        # RapidOCR uses ONNX runtime (CPU-based), device param accepted for interface consistency
        logger.info("Initializing RapidOCR engine...")
        self._reader = RapidOCR()

    @staticmethod
    def is_available() -> bool:
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa
            return True
        except ImportError:
            return False

    def ocr_image(self, image_bytes: bytes) -> str:
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)
        result, _ = self._reader(img_array)
        lines = []
        if result:
            for item in result:
                if item and len(item) >= 2:
                    lines.append(str(item[1]))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# EasyOCR engine
# ---------------------------------------------------------------------------

class EasyOcrEngine(OcrEngine):
    name = "easyocr"

    def __init__(self, device: Optional[str] = None):
        import easyocr  # noqa

        use_gpu = device != "cpu"
        if device == "gpu":
            try:
                import torch
                if not torch.cuda.is_available():
                    logger.warning("GPU requested but CUDA not available for EasyOCR, falling back to CPU")
                    use_gpu = False
            except ImportError:
                use_gpu = False

        logger.info(f"Initializing EasyOCR engine (gpu={use_gpu}, may download models on first run)...")
        try:
            self._reader = easyocr.Reader(["en", "ch_sim"], gpu=use_gpu, verbose=False)
        except (RuntimeError, Exception) as e:
            if _is_cuda_oom(e) and use_gpu:
                logger.warning(f"GPU memory insufficient for EasyOCR, retrying on CPU: {e}")
                self._reader = easyocr.Reader(["en", "ch_sim"], gpu=False, verbose=False)
            else:
                raise

    @staticmethod
    def is_available() -> bool:
        try:
            import easyocr  # noqa
            return True
        except ImportError:
            return False

    def ocr_image(self, image_bytes: bytes) -> str:
        result = self._reader.readtext(image_bytes, detail=0)
        return "\n".join(result) if result else ""


# ---------------------------------------------------------------------------
# Tesseract engine
# ---------------------------------------------------------------------------

class TesseractOcrEngine(OcrEngine):
    name = "tesseract"

    def __init__(self, device: Optional[str] = None):
        import pytesseract  # noqa
        # Tesseract is CPU-only, device param accepted for interface consistency
        logger.info("Initializing Tesseract OCR engine...")
        pytesseract.get_tesseract_version()
        self._pytesseract = pytesseract

    @staticmethod
    def is_available() -> bool:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except (ImportError, Exception):
            return False

    def ocr_image(self, image_bytes: bytes) -> str:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        text = self._pytesseract.image_to_string(img, lang="eng+chi_sim")
        return text if text else ""


# ---------------------------------------------------------------------------
# Engine registry
# ---------------------------------------------------------------------------

_ENGINE_CLASSES = {
    "surya": SuryaOcrEngine,
    "paddleocr": PaddleOcrEngine,
    "rapidocr": RapidOcrEngine,
    "easyocr": EasyOcrEngine,
    "tesseract": TesseractOcrEngine,
}


def get_available_engines() -> List[str]:
    """Return list of installed OCR engine names, in priority order."""
    available = []
    for name in ENGINE_PRIORITY:
        cls = _ENGINE_CLASSES.get(name)
        if cls and cls.is_available():
            available.append(name)
    return available


def get_ocr_engine(engine_name: Optional[str] = None, device: Optional[str] = None) -> Optional[OcrEngine]:
    """
    Return an OcrEngine instance.

    Args:
        engine_name: Specific engine to use, or None for auto-detect
                     (picks the highest-priority installed engine).
        device: Device preference: "cpu", "gpu", or None (auto: try GPU, fall back to CPU).

    Returns:
        OcrEngine instance, or None if no engine available.
    """
    cache_key = (engine_name, device)

    if engine_name:
        if cache_key in _engine_cache:
            return _engine_cache[cache_key]
        cls = _ENGINE_CLASSES.get(engine_name)
        if cls and cls.is_available():
            try:
                instance = cls(device=device)
                _engine_cache[cache_key] = instance
                return instance
            except Exception as e:
                logger.warning(f"Failed to initialize {engine_name}: {e}")
                return None
        logger.warning(f"OCR engine '{engine_name}' is not available")
        return None

    # Auto-detect: try each engine in priority order
    for name in ENGINE_PRIORITY:
        key = (name, device)
        if key in _engine_cache:
            return _engine_cache[key]
        cls = _ENGINE_CLASSES.get(name)
        if cls and cls.is_available():
            try:
                instance = cls(device=device)
                _engine_cache[key] = instance
                return instance
            except Exception as e:
                logger.warning(f"Failed to initialize {name}: {e}")
                continue

    return None


def clear_engine_cache():
    """Clear all cached engine instances. Useful for testing."""
    _engine_cache.clear()


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_text_with_ocr(
    pdf_path: str,
    max_pages: int = OCR_DEFAULT_MAX_PAGES,
    dpi: int = OCR_DEFAULT_DPI,
    engine_name: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """
    Extract text from a PDF using OCR.

    Renders each page to an image via PyMuPDF, then runs OCR on it.

    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to process
        dpi: Rendering resolution (higher = more accurate but slower)
        engine_name: Specific OCR engine, or None for auto-detect
        device: Device preference: "cpu", "gpu", or None (auto)

    Returns:
        Extracted text, or empty string on failure
    """
    try:
        import fitz
    except ImportError:
        logger.error("PyMuPDF is required for OCR extraction")
        return ""

    engine = get_ocr_engine(engine_name, device=device)
    if engine is None:
        logger.debug("No OCR engine available")
        return ""

    logger.info(f"OCR: processing {pdf_path} with {engine.name} (up to {max_pages} pages, {dpi} dpi)")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.error(f"Cannot open PDF {pdf_path}: {e}")
        return ""

    pages_to_read = min(len(doc), max_pages)
    all_text = []

    for i in range(pages_to_read):
        try:
            page = doc[i]
            # Render page to PNG image bytes
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            image_bytes = pix.tobytes("png")

            text = engine.ocr_image(image_bytes)
            if text and text.strip():
                all_text.append(text.strip())
                logger.debug(f"  Page {i+1}: extracted {len(text)} chars")
        except Exception as e:
            logger.warning(f"  OCR failed on page {i+1} of {pdf_path}: {e}")

    doc.close()

    combined = "\n".join(all_text)
    logger.info(f"OCR: extracted {len(combined)} chars total from {pages_to_read} pages")
    return combined
