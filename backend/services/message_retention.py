"""Retention policy for the short-lived message inbox."""
from datetime import datetime, timedelta

from database import messages_col, opportunities_col
from services.pdf_service import delete_stored_document


async def purge_expired_messages(retention_days: int) -> int:
    """Delete old raw messages while preserving documents used by opportunities."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    expired = await messages_col().find(
        {"message_date": {"$lt": cutoff}},
        {"attachment_storage_key": 1},
    ).to_list(length=None)
    keys = {item.get("attachment_storage_key") for item in expired if item.get("attachment_storage_key")}

    result = await messages_col().delete_many({"message_date": {"$lt": cutoff}})

    # Keep a source document when any opportunity still references it. Files
    # belonging only to purged, irrelevant messages are removed as well.
    for key in keys:
        still_used = await opportunities_col().count_documents({"source_document_key": key})
        if not still_used:
            delete_stored_document(key)

    print(f"[Retention] Deleted {result.deleted_count} messages older than {retention_days} days.")
    return result.deleted_count
