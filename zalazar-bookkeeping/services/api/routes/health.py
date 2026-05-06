from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from zalazar.db import get_db

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health_check(session: AsyncSession = Depends(get_db)):
    """Health check endpoint returning system status."""
    health_status = {"status": "ok"}
    
    # 1. Check DB
    try:
        await session.execute(text("SELECT 1"))
        health_status["database"] = "ok"
    except Exception as e:
        health_status["database"] = "down"
        health_status["status"] = "degraded"
        health_status["database_error"] = str(e)
        
    # 2. Check Review Queue Depth
    try:
        res = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE status IN ('ai_suggested', 'flagged', 'pending_review')"))
        health_status["review_queue_depth"] = res.scalar()
    except Exception:
        pass
        
    # 3. Last Sync / Job Status
    try:
        res = await session.execute(text("SELECT status, ended_at FROM job_runs WHERE job_name = 'plaid_daily_sync' ORDER BY started_at DESC LIMIT 1"))
        row = res.fetchone()
        if row:
            health_status["last_sync_status"] = row.status
            health_status["last_sync_time"] = row.ended_at
    except Exception:
        pass

    return health_status
