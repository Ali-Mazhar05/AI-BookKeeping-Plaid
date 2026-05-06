from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from zalazar.db import get_db

router = APIRouter(prefix="/meta", tags=["meta"])

@router.get("/accounts")
async def get_accounts(session: AsyncSession = Depends(get_db)):
    """Fetch all assignable chart of accounts."""
    query = text("SELECT id, code, name, account_type FROM accounts WHERE is_assignable = TRUE ORDER BY code ASC")
    result = await session.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}

@router.get("/properties")
async def get_properties(session: AsyncSession = Depends(get_db)):
    """Fetch all active properties."""
    query = text("SELECT id, name, address FROM properties WHERE is_active = TRUE ORDER BY name ASC")
    result = await session.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}

@router.get("/bank-accounts")
async def get_bank_accounts(session: AsyncSession = Depends(get_db)):
    """Fetch all active bank accounts."""
    query = text("""
        SELECT id, bank_name, account_name, account_last4, 
               CASE 
                   WHEN source_type = 'manual_entry' THEN COALESCE((SELECT SUM(amount) FROM transactions WHERE bank_account_id = bank_accounts.id), 0)
                   ELSE current_balance 
               END as current_balance, 
               last_synced_at 
        FROM bank_accounts 
        WHERE is_active = TRUE
    """)
    result = await session.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}

@router.get("/months")
async def get_available_months(entity_id: str, session: AsyncSession = Depends(get_db)):
    """Fetch all unique months that have transactions for a given entity."""
    query = text("""
        SELECT DISTINCT TO_CHAR(transaction_date, 'YYYY-MM') as month_val
        FROM transactions
        WHERE entity_id = :entity_id
        ORDER BY month_val DESC
    """)
    result = await session.execute(query, {"entity_id": entity_id})
    months = result.fetchall()
    
    # Format for frontend: [{"value": "2025-12", "label": "December 2025"}, ...]
    import calendar
    formatted_months = []
    for m in months:
        val = m.month_val
        year, month = val.split('-')
        month_name = calendar.month_name[int(month)]
        formatted_months.append({
            "value": val,
            "label": f"{month_name} {year}"
        })
    
    return {"data": formatted_months}
