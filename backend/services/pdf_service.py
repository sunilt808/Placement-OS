"""
services/pdf_service.py — Multi-library document text extraction.

Extraction chain:
  PDF:  PyMuPDF (fitz) → pdfplumber (fallback)
  DOCX: python-docx
  TXT:  direct decode
  HTML: BeautifulSoup

Returns a dict: { text, filename, mime_type, size_bytes }
so the pipeline can store the source document name on the opportunity.
"""
import asyncio
import hashlib
import io
import re
from pathlib import Path
from typing import Optional, Dict, Any

# ── PDF libraries ──────────────────────────────────────────────────────────────
try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False

try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

# ── DOCX ──────────────────────────────────────────────────────────────────────
try:
    from docx import Document as DocxDocument
    _HAS_DOCX = True
except ImportError:
    _HAS_DOCX = False

# ── HTML ──────────────────────────────────────────────────────────────────────
try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

MAX_TEXT_LENGTH = 15000  # generous limit for 3–18 page JDs
DOCUMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "documents"


def _store_document(file_bytes: bytes, filename: str) -> str:
    """Persist the source attachment with a safe, content-addressed name."""
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name) or "attachment"
    storage_key = f"{hashlib.sha256(file_bytes).hexdigest()[:16]}_{safe_name}"
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DOCUMENTS_DIR / storage_key
    if not path.exists():
        path.write_bytes(file_bytes)
    return storage_key


def stored_document_path(storage_key: str) -> Optional[Path]:
    if not storage_key or Path(storage_key).name != storage_key:
        return None
    path = (DOCUMENTS_DIR / storage_key).resolve()
    try:
        path.relative_to(DOCUMENTS_DIR.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def delete_stored_document(storage_key: str) -> None:
    path = stored_document_path(storage_key)
    if path:
        path.unlink()


def _get_filename_from_message(message) -> Optional[str]:
    """Extract original filename from Telegram document attributes."""
    try:
        doc = message.media.document
        for attr in doc.attributes:
            fn = getattr(attr, "file_name", None)
            if fn:
                return fn
    except Exception:
        pass
    return None


def _extract_pdf_fitz(pdf_bytes: bytes) -> str:
    """Primary PDF extractor using PyMuPDF."""
    text_parts = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()


def _extract_pdf_pdfplumber(pdf_bytes: bytes) -> str:
    """Fallback PDF extractor using pdfplumber."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text_parts.append(extracted)
    return "\n".join(text_parts).strip()


def _extract_pdf(pdf_bytes: bytes) -> str:
    """Try PyMuPDF first, then pdfplumber."""
    if _HAS_FITZ:
        try:
            text = _extract_pdf_fitz(pdf_bytes)
            if text:
                print("[PDF] Extracted with PyMuPDF (primary)")
                return text
        except Exception as e:
            print(f"[PDF] PyMuPDF failed: {e}, trying pdfplumber...")

    if _HAS_PDFPLUMBER:
        try:
            text = _extract_pdf_pdfplumber(pdf_bytes)
            if text:
                print("[PDF] Extracted with pdfplumber (fallback)")
                return text
        except Exception as e:
            print(f"[PDF] pdfplumber also failed: {e}")

    return ""


def _extract_docx(docx_bytes: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    if not _HAS_DOCX:
        return ""
    try:
        doc = DocxDocument(io.BytesIO(docx_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()
    except Exception as e:
        print(f"[PDF] DOCX extraction failed: {e}")
        return ""


def _extract_html(html_bytes: bytes) -> str:
    """Extract text from HTML using BeautifulSoup."""
    if not _HAS_BS4:
        return html_bytes.decode("utf-8", errors="ignore")
    try:
        soup = BeautifulSoup(html_bytes, "lxml")
        return soup.get_text(separator="\n").strip()
    except Exception as e:
        print(f"[PDF] HTML extraction failed: {e}")
        return html_bytes.decode("utf-8", errors="ignore")


async def download_and_extract_pdf(client, message) -> Optional[Dict[str, Any]]:
    """
    Downloads a document from a Telegram message and extracts text locally.

    Returns:
        {
            "text": str,           # extracted text content
            "filename": str,       # original filename e.g. "Accenture_JD.pdf"
            "mime_type": str,      # e.g. "application/pdf"
            "size_bytes": int,
        }
        or None if extraction fails or yields no text.
    """
    if not message.media or not getattr(message.media, "document", None):
        return None

    doc = message.media.document
    mime_type = getattr(doc, "mime_type", "") or ""
    size_bytes = getattr(doc, "size", 0)
    filename = _get_filename_from_message(message) or "attachment"

    # Determine supported types
    is_pdf = mime_type == "application/pdf" or filename.lower().endswith(".pdf")
    is_docx = mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ) or filename.lower().endswith((".docx", ".doc"))
    is_html = mime_type in ("text/html",) or filename.lower().endswith((".html", ".htm"))
    is_txt = mime_type in ("text/plain",) or filename.lower().endswith(".txt")

    if not (is_pdf or is_docx or is_html or is_txt):
        print(f"[PDF] Unsupported mime type: {mime_type} ({filename})")
        return None

    print(f"[PDF] Downloading: {filename} ({size_bytes} bytes, {mime_type})")

    try:
        file_bytes = await client.download_media(message, file=bytes)
        if not file_bytes:
            print("[PDF] Failed to download file bytes.")
            return None
    except Exception as e:
        print(f"[PDF] Download error: {e}")
        return None

    storage_key = await asyncio.to_thread(_store_document, file_bytes, filename)

    # Extract based on type
    def _extract_sync():
        if is_pdf:
            return _extract_pdf(file_bytes)
        elif is_docx:
            return _extract_docx(file_bytes)
        elif is_html:
            return _extract_html(file_bytes)
        elif is_txt:
            return file_bytes.decode("utf-8", errors="ignore").strip()
        return ""

    try:
        extracted_text = await asyncio.to_thread(_extract_sync)
    except Exception as e:
        print(f"[PDF] Extraction error: {e}")
        return None

    if not extracted_text:
        print("[PDF] Extraction yielded no text (possibly image-only or encrypted); source retained.")

    print(f"[PDF] Extracted {len(extracted_text)} chars from '{filename}'")

    # Truncate very long documents
    if len(extracted_text) > MAX_TEXT_LENGTH:
        print(f"[PDF] Truncating to {MAX_TEXT_LENGTH} chars")
        extracted_text = extracted_text[:MAX_TEXT_LENGTH] + "\n\n... [TRUNCATED]"

    return {
        "text": extracted_text,
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "storage_key": storage_key,
        "text_extracted": bool(extracted_text),
    }
