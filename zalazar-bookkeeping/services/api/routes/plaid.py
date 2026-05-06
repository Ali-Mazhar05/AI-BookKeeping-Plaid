from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter(prefix="/plaid", tags=["plaid"])


class SyncRequest(BaseModel):
    entity_id: str


@router.post("/sync")
async def trigger_sync(req: SyncRequest, background_tasks: BackgroundTasks):
    """Re-classify all pending/flagged transactions for the entity."""
    from zalazar.plaid.sync import reclassify_transactions
    background_tasks.add_task(reclassify_transactions, req.entity_id)
    return {"status": "sync_initiated"}
