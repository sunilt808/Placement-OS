"""
api/routes/import_.py — Historical Telegram export upload endpoint.
Supports JSON, TXT, HTML. Streams progress via SSE.
"""
import asyncio
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse

from services.telegram_importer import import_telegram_export
from api.routes.auth import require_auth

router = APIRouter(prefix="/api/import", tags=["import"],
                   dependencies=[Depends(require_auth)])


@router.post("/upload")
async def upload_telegram_export(file: UploadFile = File(...)):
    """
    Upload and process a Telegram export file.
    Returns a StreamingResponse (SSE) with live progress updates.
    """
    allowed_extensions = {".json", ".txt", ".html", ".htm"}
    fname = file.filename or ""
    ext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""

    if ext not in allowed_extensions:
        raise HTTPException(400, f"Unsupported file type: {ext}. Use .json, .txt, or .html")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")

    progress_queue: asyncio.Queue = asyncio.Queue()

    async def progress_callback(stats: dict):
        await progress_queue.put(stats)

    async def run_import():
        try:
            final_stats = await import_telegram_export(content, fname, progress_callback)
            await progress_queue.put({"done": True, **final_stats})
        except Exception as e:
            await progress_queue.put({"error": str(e), "done": True})

    async def generate():
        task = asyncio.create_task(run_import())
        while True:
            try:
                stats = await asyncio.wait_for(progress_queue.get(), timeout=60.0)
                yield f"data: {json.dumps(stats)}\n\n"
                if stats.get("done"):
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
        await task

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/status")
async def get_import_status():
    """Get status of recent imports (from messages collection)."""
    from database import messages_col
    from datetime import datetime, timedelta

    col = messages_col()
    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent_historical = await col.count_documents({
        "source": "HISTORICAL",
        "message_date": {"$gte": cutoff}
    })
    total_historical = await col.count_documents({"source": "HISTORICAL"})
    return {
        "total_historical_messages": total_historical,
        "imported_last_24h": recent_historical,
    }
