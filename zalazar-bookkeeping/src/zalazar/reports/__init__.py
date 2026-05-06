from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import structlog
from ..db import AsyncSessionLocal
from datetime import datetime

logger = structlog.get_logger()

# In-memory lock for debouncing
_refresh_task = None

async def refresh_monthly_pnl():
    """
    Refreshes the monthly_property_pnl materialized view.
    """
    async with AsyncSessionLocal() as session:
        try:
            # We use CONCURRENTLY so it doesn't block reads. 
            # Note: Requires a unique index, which we have.
            await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_property_pnl"))
            await session.commit()
            logger.info("Materialized view monthly_property_pnl refreshed")
        except Exception as e:
            logger.error("Failed to refresh materialized view", error=str(e))
            await session.rollback()

async def maybe_refresh_monthly_pnl():
    """
    Debounced refresh. If a refresh is already scheduled, it does nothing.
    Otherwise, schedules a refresh in 5 minutes.
    """
    global _refresh_task
    
    if _refresh_task and not _refresh_task.done():
        logger.info("Refresh already scheduled, skipping debounce")
        return

    async def delayed_refresh():
        await asyncio.sleep(300) # 5 minutes
        await refresh_monthly_pnl()

    _refresh_task = asyncio.create_task(delayed_refresh())
    logger.info("Scheduled monthly_property_pnl refresh in 300s")

async def get_monthly_pnl(session: AsyncSession, entity_id: str, property_id: str = None, start_date: str = None, end_date: str = None):
    """
    Queries the monthly_property_pnl view.
    """
    query = """
        SELECT * FROM monthly_property_pnl
        WHERE entity_id = :entity_id
    """
    params = {"entity_id": entity_id}
    
    if property_id:
        query += " AND property_id = :property_id"
        params["property_id"] = property_id
        
    if start_date:
        query += " AND month >= :start_date"
        params["start_date"] = start_date
        
    if end_date:
        query += " AND month <= :end_date"
        params["end_date"] = end_date
        
    query += " ORDER BY month DESC, account_code"
    
    result = await session.execute(text(query), params)
    return [dict(r._mapping) for r in result.fetchall()]
