from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from zalazar.db import get_db, AsyncSessionLocal
from zalazar.plaid.link import ExchangeTokenRequest, create_link_token, exchange_public_token_and_save
from zalazar.plaid.sync import reclassify_transactions, sync_account
from zalazar.plaid.webhooks import verify_webhook_signature, handle_webhook
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/plaid", tags=["plaid"])


class SyncRequest(BaseModel):
    entity_id: str


class LinkTokenRequest(BaseModel):
    entity_id: str


@router.post("/link-token")
async def get_link_token(req: LinkTokenRequest):
    """Creates a Plaid Link token for the UI."""
    try:
        token = await create_link_token(req.entity_id)
        return {"link_token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exchange-token")
async def exchange_token(
    req: ExchangeTokenRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    """Exchanges a public token, saves account info, and triggers an initial sync."""
    try:
        result = await exchange_public_token_and_save(session, req)
        await session.commit()

        # Resolve plaid_account_ids → our DB ids, then kick off initial sync per account
        plaid_ids = [a["account_id"] for a in result.get("accounts", [])]
        if plaid_ids:
            id_rows = await session.execute(
                text("SELECT id FROM bank_accounts WHERE plaid_account_id = ANY(:ids)"),
                {"ids": plaid_ids},
            )
            for row in id_rows.fetchall():
                background_tasks.add_task(sync_account, str(row.id))

        return result
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def trigger_sync(req: SyncRequest, background_tasks: BackgroundTasks):
    """Re-classify all pending/flagged transactions for the entity."""
    background_tasks.add_task(reclassify_transactions, req.entity_id)
    return {"status": "sync_initiated"}


@router.post("/webhooks")
async def plaid_webhooks(request: Request, background_tasks: BackgroundTasks):
    """Receives real-time Plaid transaction events (SYNC_UPDATES_AVAILABLE, ITEM_LOGIN_REQUIRED, etc.)."""
    if not await verify_webhook_signature(request):
        raise HTTPException(status_code=401, detail="Invalid Plaid webhook signature")
    payload = await request.json()
    background_tasks.add_task(_handle_webhook_bg, payload)
    return {"received": True}


async def _handle_webhook_bg(payload: dict):
    async with AsyncSessionLocal() as session:
        try:
            await handle_webhook(session, payload)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Webhook background handler failed", error=str(e))
