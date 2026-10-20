"""
services/image_ocr.py — Offline OCR for photo announcements (JPG/PNG).

College posts posters/screenshots as images. Uses pytesseract (Tesseract
engine runs locally on this machine — no API, no quota, free forever).

Graceful degradation: if Tesseract isn't installed, returns None and the
message flows through as caption-text-only. Install once:
    1. pip install pytesseract pillow
    2. Windows: install https://github.com/UB-Mannheim/tesseract/wiki
       Linux: apt install tesseract-ocr
"""
import asyncio
from typing import Any, Dict, Optional

try:
    import pytesseract
    from PIL import Image
    import io
    _HAS_OCR = True
except ImportError:
    _HAS_OCR = False


def _ocr_bytes(data: bytes) -> str:
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("L", "RGB"):
        img = img.convert("RGB")
    return (pytesseract.image_to_string(img) or "").strip()


async def ocr_image_bytes(data: bytes) -> Optional[str]:
    """OCR raw image bytes. Returns None when unavailable or empty."""
    if not _HAS_OCR:
        print("[OCR] pytesseract/Pillow not installed — skipping image OCR")
        return None
    try:
        text = await asyncio.to_thread(_ocr_bytes, data)
        if text:
            print(f"[OCR] Extracted {len(text)} chars from image")
        else:
            print("[OCR] Image yielded no text")
        return text or None
    except Exception as e:
        print(f"[OCR] Failed: {e}")
        return None


async def _ocr_with_gemini_vision(data: bytes) -> Optional[str]:
    """Fallback OCR via Gemini vision. Used only when local OCR finds nothing."""
    try:
        from services.ai_service import _gemini_client, genai_types
        from config import settings
    except Exception as e:
        print(f"[OCR] Gemini vision unavailable: {e}")
        return None
    if not _gemini_client:
        return None
    try:
        from google.genai import types as _types
        resp = await asyncio.to_thread(
            _gemini_client.models.generate_content,
            model=settings.gemini_flash_model,
            contents=[
                "Extract ALL visible text from this placement announcement image. "
                "Return plain text only, preserving line breaks.",
                _types.Part.from_bytes(data=data, mime_type="image/jpeg"),
            ],
        )
        text = getattr(resp, "text", None) or ""
        text = text.strip()
        if text:
            print(f"[OCR] Gemini vision fallback extracted {len(text)} chars")
        return text or None
    except Exception as e:
        print(f"[OCR] Gemini vision fallback failed: {e}")
        return None


async def ocr_image_bytes_with_fallback(data: bytes) -> Optional[str]:
    """
    Local-first OCR: Tesseract first, Gemini vision only if local yields nothing.

    Keeps local deterministic extraction as the source of truth while still
    catching image-only posters on machines without Tesseract installed.
    """
    text = await ocr_image_bytes(data)
    if text:
        return text
    return await _ocr_with_gemini_vision(data)
