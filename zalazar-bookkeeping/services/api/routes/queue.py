from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
import uuid
from zalazar.db import get_db

router = APIRouter(prefix="/queue", tags=["queue"])

QUEUE_SELECT = """
    SELECT
        t.id, t.transaction_date, t.amount,
        t.vendor_name_clean, t.status, t.account_id,
        t.categorization_reason,
        ac.name as category_name,
        b.bank_name, b.account_last4,
        STRING_AGG(DISTINCT p.name, ', ') as property_names
    FROM transactions t
    LEFT JOIN accounts ac ON t.account_id = ac.id
    LEFT JOIN bank_accounts b ON t.bank_account_id = b.id
    LEFT JOIN transaction_allocations ta ON ta.transaction_id = t.id
    LEFT JOIN properties p ON ta.property_id = p.id
    WHERE t.status IN ('pending_review', 'flagged', 'ai_suggested')
    GROUP BY t.id, t.transaction_date, t.amount, t.vendor_name_clean, t.status,
             t.account_id, t.categorization_reason, ac.name, b.bank_name, b.account_last4
    ORDER BY t.transaction_date DESC
"""


@router.get("/stats")
async def get_queue_stats(entity_id: Optional[str] = None, session: AsyncSession = Depends(get_db)):
    where_sql = " WHERE status IN ('pending_review', 'flagged', 'ai_suggested') "
    params = {}
    if entity_id:
        where_sql += " AND entity_id = :entity_id "
        params["entity_id"] = entity_id

    pending_res = await session.execute(
        text(f"SELECT COUNT(*) FROM transactions {where_sql}"),
        params
    )
    
    reviewed_where = " WHERE status = 'reviewed' AND updated_at::date = CURRENT_DATE "
    if entity_id:
        reviewed_where += " AND entity_id = :entity_id "

    reviewed_res = await session.execute(
        text(f"SELECT COUNT(*) FROM transactions {reviewed_where}"),
        params
    )
    return {
        "pending_count": pending_res.scalar(),
        "reviewed_today": reviewed_res.scalar()
    }


@router.get("/")
async def get_queue(entity_id: Optional[str] = None, session: AsyncSession = Depends(get_db)):
    sql = QUEUE_SELECT
    params = {}
    if entity_id:
        # In QUEUE_SELECT, the WHERE is on line 24. We need to inject the entity filter.
        sql = sql.replace("WHERE t.status", "WHERE t.entity_id = :entity_id AND t.status")
        params["entity_id"] = entity_id
        
    result = await session.execute(text(sql), params)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


class CorrectionRequest(BaseModel):
    account_id: str
    allocations: List[dict]


@router.post("/{tx_id}/approve")
async def approve_transaction(tx_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    try:
        tx_res = await session.execute(
            text("""
                UPDATE transactions SET status = 'reviewed', updated_at = NOW()
                WHERE id = :id AND status IN ('pending_review', 'flagged', 'ai_suggested')
                RETURNING id, entity_id, amount
            """),
            {"id": tx_id}
        )
        tx = tx_res.fetchone()
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found in queue")

        # Ensure every approved transaction has at least one allocation entry so it
        # counts toward DSCR. If allocations already exist (e.g. from auto_categorized
        # via a vendor rule), skip. Otherwise spread evenly across active properties.
        existing = await session.execute(
            text("SELECT 1 FROM transaction_allocations WHERE transaction_id = :tid LIMIT 1"),
            {"tid": tx.id}
        )
        if not existing.fetchone():
            props = await session.execute(
                text("SELECT id FROM properties WHERE entity_id = :eid AND is_active = TRUE ORDER BY name"),
                {"eid": tx.entity_id}
            )
            property_ids = [r.id for r in props.fetchall()]
            if property_ids:
                from decimal import Decimal, ROUND_HALF_EVEN
                n = len(property_ids)
                amount = Decimal(str(tx.amount))
                per = (amount / n).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
                for i, pid in enumerate(property_ids):
                    alloc_amt = per
                    if i == n - 1:
                        alloc_amt = amount - per * (n - 1)
                    await session.execute(
                        text("""
                            INSERT INTO transaction_allocations
                                (transaction_id, property_id, amount, percentage, method)
                            VALUES (:tid, :pid, :amt, :pct, 'even_split')
                        """),
                        {"tid": tx.id, "pid": pid, "amt": alloc_amt, "pct": round(100.0 / n, 4)}
                    )

        await session.commit()
        return {"status": "approved"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tx_id}/exclude")
async def exclude_transaction(tx_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(
            text("UPDATE transactions SET status = 'excluded', updated_at = NOW() WHERE id = :id RETURNING id"),
            {"id": tx_id}
        )
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Transaction not found")
        await session.commit()
        return {"status": "excluded"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tx_id}/correct")
async def correct_transaction(tx_id: uuid.UUID, req: CorrectionRequest, session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(
            text("""
                UPDATE transactions
                SET account_id = :account_id, status = 'reviewed', updated_at = NOW()
                WHERE id = :id
                RETURNING id
            """),
            {"account_id": req.account_id, "id": tx_id}
        )
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Transaction not found")

        await session.execute(
            text("DELETE FROM transaction_allocations WHERE transaction_id = :id"),
            {"id": tx_id}
        )
        for alloc in req.allocations:
            await session.execute(
                text("""
                    INSERT INTO transaction_allocations (transaction_id, property_id, amount, method)
                    VALUES (:tid, :pid, :amt, 'manual')
                """),
                {"tid": tx_id, "pid": alloc["property_id"], "amt": alloc["amount"]}
            )

        await session.commit()
        return {"status": "corrected"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
