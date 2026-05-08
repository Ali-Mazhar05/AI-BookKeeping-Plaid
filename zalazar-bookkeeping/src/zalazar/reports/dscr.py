from typing import Dict, Any, Optional
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
import structlog

logger = structlog.get_logger()

async def calculate_property_dscr(
    session: AsyncSession, 
    property_id: str, 
    start_date: date, 
    end_date: date
) -> Dict[str, Any]:
    """
    DSCR = Net Operating Income / Debt Service
    
    NOI = (Rental Income + Other Income) - Operating Expenses
    Operating Expenses EXCLUDE: Loan Principal, CapEx, Depreciation, Amortization.
    
    Debt Service = Total Mortgage Payments (Interest + Principal)
    """
    
    # 1. Fetch all allocations for this property in period
    query = text("""
        SELECT a.amount, acct.account_type, acct.name as account_name
        FROM transaction_allocations a
        JOIN transactions t ON a.transaction_id = t.id
        JOIN accounts acct ON t.account_id = acct.id
        WHERE a.property_id = :pid
          AND t.transaction_date BETWEEN :start AND :end
          AND t.status != 'excluded'
    """)
    
    res = await session.execute(query, {"pid": property_id, "start": start_date, "end": end_date})
    rows = res.fetchall()
    
    income = Decimal('0.00')
    operating_expenses = Decimal('0.00')
    interest = Decimal('0.00')
    principal = Decimal('0.00')
    
    for row in rows:
        amt = Decimal(str(row.amount))

        if row.account_type == 'income':
            # Positive amt = income received; negative = refund/reversal, still correct as signed
            income += amt
        elif row.account_type == 'operating_expense':
            # Always treat as cost regardless of sign
            operating_expenses += abs(amt)
        elif row.account_type == 'property_cost':
            if row.account_name == 'Mortgage Interest':
                interest += abs(amt)
            elif row.account_name in ('Capital Improvements', 'Furniture / Equipment'):
                # CapEx excluded from NOI but included as operating expense for visibility
                operating_expenses += abs(amt)
            else:
                operating_expenses += abs(amt)
        elif row.account_type == 'capital_non_expense':
            # Principal Reduction counts toward debt service; Owner Contributions/Distributions excluded
            if row.account_name == 'Principal Reduction':
                principal += abs(amt)
            # Owner Contributions / Distributions are balance-sheet items — excluded from DSCR

    noi = income - operating_expenses
    debt_service = interest + principal
    
    dscr = Decimal('0.00')
    if debt_service > 0:
        dscr = (noi / debt_service).quantize(Decimal('0.01'))
        
    return {
        "property_id": property_id,
        "period": {"start": str(start_date), "end": str(end_date)},
        "metrics": {
            "income": float(income),
            "operating_expenses": float(operating_expenses),
            "noi": float(noi),
            "interest": float(interest),
            "principal": float(principal),
            "total_debt_service": float(debt_service)
        },
        "dscr": float(dscr)
    }
