from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from zalazar.db import get_db

router = APIRouter(prefix="/meta", tags=["meta"])


class PropertyCreate(BaseModel):
    entity_id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None


class AccountCreate(BaseModel):
    code: str
    name: str
    account_type: str  # income | operating_expense | property_cost | capital_non_expense | transfer | other
    is_pnl: bool = True


# ─── Accounts / Categories ────────────────────────────────────────────────────

@router.get("/accounts")
async def get_accounts(session: AsyncSession = Depends(get_db)):
    """Fetch all assignable chart of accounts, with their transaction counts."""
    query = text("""
        SELECT a.id, a.code, a.name, a.account_type,
               (SELECT COUNT(*) FROM transactions t WHERE t.account_id = a.id) AS tx_count
        FROM accounts a
        WHERE a.is_assignable = TRUE
        ORDER BY a.code ASC
    """)
    result = await session.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


@router.get("/accounts/inactive")
async def get_inactive_accounts(session: AsyncSession = Depends(get_db)):
    """Fetch all non-assignable (hidden) chart of accounts, with their transaction counts."""
    query = text("""
        SELECT a.id, a.code, a.name, a.account_type,
               (SELECT COUNT(*) FROM transactions t WHERE t.account_id = a.id) AS tx_count
        FROM accounts a
        WHERE a.is_assignable = FALSE
        ORDER BY a.code ASC
    """)
    result = await session.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


@router.post("/accounts", status_code=201)
async def create_account(body: AccountCreate, session: AsyncSession = Depends(get_db)):
    """Create a new chart-of-accounts category."""
    try:
        result = await session.execute(
            text("""
                INSERT INTO accounts (code, name, account_type, is_pnl, is_assignable)
                VALUES (:code, :name, :account_type, :is_pnl, TRUE)
                RETURNING id, code, name, account_type, is_assignable
            """),
            {
                "code": body.code.strip(),
                "name": body.name.strip(),
                "account_type": body.account_type,
                "is_pnl": body.is_pnl,
            }
        )
        await session.commit()
        return {"data": dict(result.fetchone()._mapping)}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create category: {str(e)}")


@router.get("/accounts/{account_id}/tx-count")
async def get_account_tx_count(account_id: str, session: AsyncSession = Depends(get_db)):
    """Count transactions assigned to a given account/category."""
    result = await session.execute(
        text("SELECT COUNT(*) as count FROM transactions WHERE account_id = :id"),
        {"id": account_id}
    )
    row = result.fetchone()
    return {"count": row.count if row else 0}


@router.patch("/accounts/{account_id}/assignable")
async def toggle_account_assignable(account_id: str, session: AsyncSession = Depends(get_db)):
    """Toggle the is_assignable flag on an account (show/hide from dropdowns)."""
    result = await session.execute(
        text("UPDATE accounts SET is_assignable = NOT is_assignable WHERE id = :id RETURNING id, is_assignable"),
        {"id": account_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")
    await session.commit()
    return {"id": str(row.id), "is_assignable": row.is_assignable}


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: str, session: AsyncSession = Depends(get_db)):
    """Permanently delete a category. Blocked if any transactions still reference it."""
    tx_check = await session.execute(
        text("SELECT COUNT(*) as count FROM transactions WHERE account_id = :id"),
        {"id": account_id}
    )
    count = tx_check.fetchone().count
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {count} transaction(s) are still assigned to this category. Reassign them first."
        )
    result = await session.execute(
        text("DELETE FROM accounts WHERE id = :id RETURNING id"),
        {"id": account_id}
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Account not found")
    await session.commit()
    return {"success": True}


# ─── Properties ───────────────────────────────────────────────────────────────

@router.get("/properties")
async def get_properties(session: AsyncSession = Depends(get_db)):
    """Fetch all active properties."""
    query = text("SELECT id, name, address, city, state, zip FROM properties WHERE is_active = TRUE ORDER BY name ASC")
    result = await session.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


@router.get("/properties/inactive")
async def get_inactive_properties(entity_id: str, session: AsyncSession = Depends(get_db)):
    """Fetch all hidden (is_active=FALSE) properties for an entity, with their allocation counts."""
    query = text("""
        SELECT p.id, p.name, p.address, p.city, p.state, p.zip,
               (SELECT COUNT(*) FROM transaction_allocations ta WHERE ta.property_id = p.id) AS tx_count
        FROM properties p
        WHERE p.entity_id = :entity_id AND p.is_active = FALSE
        ORDER BY p.name ASC
    """)
    result = await session.execute(query, {"entity_id": entity_id})
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


@router.get("/properties/{property_id}/tx-count")
async def get_property_tx_count(property_id: str, session: AsyncSession = Depends(get_db)):
    """Count transaction allocations referencing a given property."""
    result = await session.execute(
        text("SELECT COUNT(*) as count FROM transaction_allocations WHERE property_id = :id"),
        {"id": property_id}
    )
    row = result.fetchone()
    return {"count": row.count if row else 0}


@router.post("/properties", status_code=201)
async def create_property(body: PropertyCreate, session: AsyncSession = Depends(get_db)):
    """Create a new property."""
    result = await session.execute(
        text("""
            INSERT INTO properties (entity_id, name, address, city, state, zip)
            VALUES (:entity_id, :name, :address, :city, :state, :zip)
            RETURNING id, name, address, city, state, zip
        """),
        {
            "entity_id": body.entity_id,
            "name": body.name,
            "address": body.address,
            "city": body.city,
            "state": body.state,
            "zip": body.zip,
        }
    )
    await session.commit()
    return {"data": dict(result.fetchone()._mapping)}


@router.post("/properties/{property_id}/restore", status_code=200)
async def restore_property(property_id: str, session: AsyncSession = Depends(get_db)):
    """Restore a soft-deleted property by marking it active again."""
    result = await session.execute(
        text("UPDATE properties SET is_active = TRUE, updated_at = NOW() WHERE id = :id AND is_active = FALSE RETURNING id"),
        {"id": property_id}
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Property not found or already active")
    await session.commit()
    return {"success": True}


@router.delete("/properties/{property_id}/permanent", status_code=200)
async def permanently_delete_property(property_id: str, session: AsyncSession = Depends(get_db)):
    """Permanently delete a property. Blocked if any transaction_allocations still reference it."""
    alloc_check = await session.execute(
        text("SELECT COUNT(*) as count FROM transaction_allocations WHERE property_id = :id"),
        {"id": property_id}
    )
    count = alloc_check.fetchone().count
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {count} transaction allocation(s) still reference this property. Reassign them first."
        )
    result = await session.execute(
        text("DELETE FROM properties WHERE id = :id RETURNING id"),
        {"id": property_id}
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Property not found")
    await session.commit()
    return {"success": True}


@router.delete("/properties/{property_id}", status_code=200)
async def delete_property(property_id: str, session: AsyncSession = Depends(get_db)):
    """Soft-delete a property (hide from dashboard). Blocked if allocations still reference it."""
    alloc_check = await session.execute(
        text("SELECT COUNT(*) as count FROM transaction_allocations WHERE property_id = :id"),
        {"id": property_id}
    )
    count = alloc_check.fetchone().count
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot remove property: {count} transaction allocation(s) still reference it. Reassign them first."
        )
    result = await session.execute(
        text("UPDATE properties SET is_active = FALSE, updated_at = NOW() WHERE id = :id AND is_active = TRUE RETURNING id"),
        {"id": property_id}
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Property not found")
    await session.commit()
    return {"success": True}


# ─── Bank Accounts ────────────────────────────────────────────────────────────

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


# ─── Months ───────────────────────────────────────────────────────────────────

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
