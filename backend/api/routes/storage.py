"""
api/routes/storage.py — Storage usage, retention purge and bulk deletion.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from api.routes.auth import require_auth
from services import storage_service

router = APIRouter(prefix="/api/storage", tags=["storage"],
                   dependencies=[Depends(require_auth)])


class BulkIds(BaseModel):
    ids: List[str]


class PurgeRequest(BaseModel):
    days: int = 25


@router.get("")
async def storage_stats():
    return await storage_service.get_storage_stats()


@router.post("/opportunities/delete-bulk")
async def bulk_delete_opportunities(body: BulkIds):
    deleted = await storage_service.delete_opportunities_bulk(body.ids)
    return {"ok": True, "deleted": deleted}


@router.post("/messages/delete-bulk")
async def bulk_delete_messages(body: BulkIds):
    deleted = await storage_service.delete_messages_bulk(body.ids)
    return {"ok": True, "deleted": deleted}


@router.post("/purge")
async def manual_purge(body: PurgeRequest):
    if body.days < 1 or body.days > 365:
        raise HTTPException(400, "days must be 1-365")
    summary = await storage_service.purge_older_than(body.days)
    return {"ok": True, **summary}
