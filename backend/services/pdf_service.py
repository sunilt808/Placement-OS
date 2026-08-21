import asyncio
import io
import pdfplumber
from telethon import TelegramClient

MAX_PDF_TEXT_LENGTH = 10000

async def download_and_extract_pdf(client: TelegramClient, message) -> str | None:
    """
    Downloads a PDF document from a Telegram message into memory and extracts text.
    Returns the extracted text, or None if extraction fails or yields empty text.
    Truncates text to MAX_PDF_TEXT_LENGTH to avoid overwhelming AI context.
    """
    if not message.media or not getattr(message.media, "document", None):
        return None
        
    doc = message.media.document
    mime_type = getattr(doc, "mime_type", "")
    
    # We only want to process PDFs for now
    if mime_type != "application/pdf":
        return None
        
    print(f"[PDF Service] Downloading PDF (size: {doc.size} bytes)...")
    try:
        # Download file to memory (BytesIO)
        pdf_bytes = await client.download_media(message, file=bytes)
        
        if not pdf_bytes:
            print("[PDF Service] Failed to download PDF bytes.")
            return None
            
        print("[PDF Service] PDF downloaded, extracting text...")
        
        def _extract():
            text = ""
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            return text.strip()
            
        extracted_text = await asyncio.to_thread(_extract)
        
        if not extracted_text:
            print("[PDF Service] PDF extraction yielded no text (might be an image-only PDF).")
            return None
            
        print(f"[PDF Service] Extracted {len(extracted_text)} characters from PDF.")
        
        if len(extracted_text) > MAX_PDF_TEXT_LENGTH:
            print(f"[PDF Service] Truncating text to {MAX_PDF_TEXT_LENGTH} chars.")
            extracted_text = extracted_text[:MAX_PDF_TEXT_LENGTH] + "\n\n... [TRUNCATED]"
            
        return extracted_text

    except Exception as e:
        print(f"[PDF Service] Error extracting PDF: {e}")
        return None
