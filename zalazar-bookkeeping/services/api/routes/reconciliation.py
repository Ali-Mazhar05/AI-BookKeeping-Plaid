from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
from datetime import date
from zalazar.db import AsyncSessionLocal
from zalazar.reconciler import reconcile_account

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

class ReconciliationLog(BaseModel):
    id: str
    reconciliation_date: date
    bank_account_id: str
    account_name: Optional[str] = None
    plaid_balance: float
    calculated_balance: float
    difference: float
    status: str

@router.get("/logs", response_model=List[ReconciliationLog])
async def get_reconciliation_logs(entity_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT l.*, a.account_name 
            FROM reconciliation_log l
            JOIN bank_accounts a ON l.bank_account_id = a.id
            WHERE l.entity_id = :entity_id
            ORDER BY l.created_at DESC
            LIMIT 50
        """),
        {"entity_id": entity_id}
    )
    rows = result.fetchall()
    return [
        ReconciliationLog(
            id=str(row.id),
            reconciliation_date=row.reconciliation_date,
            bank_account_id=str(row.bank_account_id),
            account_name=row.account_name,
            plaid_balance=float(row.plaid_balance),
            calculated_balance=float(row.calculated_balance),
            difference=float(row.difference),
            status=row.status
        ) for row in rows
    ]

@router.post("/trigger/{account_id}")
async def trigger_reconciliation(account_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await reconcile_account(db, account_id)
        return {"status": "success", "message": f"Reconciliation triggered for account {account_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
