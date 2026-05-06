from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
import structlog

logger = structlog.get_logger()

async def query_pnl(session: AsyncSession, entity_id: str, start_date: str, end_date: str, property_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Monthly P&L for a property or portfolio across a date range."""
    # Note: Using the granular data from transactions/allocations since the summary table lacks account-level detail
    query = """
        SELECT t.account_id, SUM(ta.amount) as amount
        FROM transactions t
        JOIN transaction_allocations ta ON t.id = ta.transaction_id
        JOIN accounts a ON a.id = t.account_id
        WHERE t.entity_id = :entity_id
          AND t.transaction_date >= :start_date AND t.transaction_date <= :end_date
          AND t.status IN ('auto_categorized', 'reviewed')
          AND a.is_pnl = TRUE
    """
    params = {"entity_id": entity_id, "start_date": start_date, "end_date": end_date}
    if property_id:
        query += " AND ta.property_id = :property_id"
        params["property_id"] = property_id
    query += " GROUP BY t.account_id"
    
    result = await session.execute(text(query), params)
    return [dict(row._mapping) for row in result.fetchall()]

async def query_transactions(session: AsyncSession, entity_id: str, start_date: str, end_date: str,
                             property_id: Optional[str] = None, account_code: Optional[str] = None,
                             min_amount: Optional[float] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """List individual transactions matching filters."""
    # This requires joining transactions and transaction_allocations
    query = """
        SELECT t.id, t.transaction_date, t.vendor_name_clean, t.amount as total_amount, 
               t.account_id, ta.property_id, ta.amount as allocated_amount
        FROM transactions t
        LEFT JOIN transaction_allocations ta ON t.id = ta.transaction_id
        WHERE t.entity_id = :entity_id
          AND t.transaction_date >= :start_date AND t.transaction_date <= :end_date
          AND t.status IN ('auto_categorized', 'reviewed')
    """
    params = {"entity_id": entity_id, "start_date": start_date, "end_date": end_date, "limit": limit}
    
    if property_id:
        query += " AND ta.property_id = :property_id"
        params["property_id"] = property_id
    if account_code:
        query += " AND t.account_id = :account_code"
        params["account_code"] = account_code
    if min_amount is not None:
        query += " AND abs(t.amount) >= :min_amount"
        params["min_amount"] = min_amount
        
    query += " ORDER BY t.transaction_date DESC LIMIT :limit"
    
    result = await session.execute(text(query), params)
    return [dict(row._mapping) for row in result.fetchall()]

async def list_properties(session: AsyncSession, entity_id: str) -> List[Dict[str, Any]]:
    """List all active properties for an entity."""
    query = "SELECT id, name FROM properties WHERE entity_id = :entity_id AND is_active = TRUE"
    result = await session.execute(text(query), {"entity_id": entity_id})
    return [dict(row._mapping) for row in result.fetchall()]

async def list_accounts(session: AsyncSession) -> List[Dict[str, Any]]:
    """List the chart of accounts (leaf accounts only)."""
    query = "SELECT code, name FROM accounts WHERE is_assignable = TRUE"
    result = await session.execute(text(query))
    return [dict(row._mapping) for row in result.fetchall()]

async def review_queue_count(session: AsyncSession, entity_id: str) -> int:
    """Return the count of transactions currently in review."""
    query = """
        SELECT COUNT(*) 
        FROM transactions 
        WHERE entity_id = :entity_id AND status IN ('ai_suggested', 'flagged', 'pending_review')
    """
    result = await session.execute(text(query), {"entity_id": entity_id})
    return result.scalar()
