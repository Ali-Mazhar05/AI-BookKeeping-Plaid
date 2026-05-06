from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel
import uuid
from zalazar.db import get_db

router = APIRouter(prefix="/transactions", tags=["transactions"])

TRANSACTION_SELECT = """
    SELECT
        t.id, t.transaction_date, t.amount,
        t.vendor_name_clean, t.vendor_name_raw as merchant_name,
        t.description_clean, t.status, t.account_id,
        ac.name as category_name, ac.code as plaid_category_primary,
        b.bank_name, b.account_last4,
        STRING_AGG(DISTINCT p.name, ', ') as property_names
    FROM transactions t
    LEFT JOIN accounts ac ON t.account_id = ac.id
    LEFT JOIN bank_accounts b ON t.bank_account_id = b.id
    LEFT JOIN transaction_allocations ta ON ta.transaction_id = t.id
    LEFT JOIN properties p ON ta.property_id = p.id
"""

GROUP_BY = """
    GROUP BY t.id, t.transaction_date, t.amount, t.vendor_name_clean, t.vendor_name_raw,
             t.description_clean, t.status, t.account_id, ac.name, ac.code, b.bank_name, b.account_last4
    ORDER BY t.transaction_date DESC
"""


@router.get("/")
async def list_transactions(
    entity_id: Optional[str] = None,
    bank_account_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    where_clauses = []
    params = {}
    
    if entity_id:
        where_clauses.append("t.entity_id = :entity_id")
        params["entity_id"] = entity_id
        
    if bank_account_id:
        where_clauses.append("t.bank_account_id = :bank_account_id")
        params["bank_account_id"] = bank_account_id
        
    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)
        
    query = text(TRANSACTION_SELECT + where_sql + GROUP_BY)
    result = await session.execute(query, params)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


class UpdateTransactionRequest(BaseModel):
    account_id: str
    allocations: List[dict]


@router.patch("/{tx_id}")
async def update_transaction(
    tx_id: uuid.UUID,
    req: UpdateTransactionRequest,
    session: AsyncSession = Depends(get_db)
):
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
                    VALUES (:tid, :pid, :amt, 'custom')
                """),
                {"tid": tx_id, "pid": alloc["property_id"], "amt": alloc["amount"]}
            )

        await session.commit()
        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tx_id}")
async def delete_transaction(tx_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    try:
        await session.execute(
            text("DELETE FROM transaction_allocations WHERE transaction_id = :id"),
            {"id": tx_id}
        )
        result = await session.execute(
            text("DELETE FROM transactions WHERE id = :id RETURNING id"),
            {"id": tx_id}
        )
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Transaction not found")
        await session.commit()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
