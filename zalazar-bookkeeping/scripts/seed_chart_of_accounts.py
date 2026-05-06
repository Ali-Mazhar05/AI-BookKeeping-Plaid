import asyncio
from sqlalchemy import text
from zalazar.db import engine, AsyncSessionLocal
from zalazar.config import settings

CHART_OF_ACCOUNTS = [
    # Income
    {"code": "INC", "name": "Income", "parent_code": None, "account_type": "income", "is_assignable": False, "is_pnl": False},
    {"code": "INC-RENT", "name": "Rental Income", "parent_code": "INC", "account_type": "income", "is_assignable": True, "is_pnl": True},
    {"code": "INC-OTHER", "name": "Other Income", "parent_code": "INC", "account_type": "income", "is_assignable": True, "is_pnl": True},
    
    # Operating Expenses
    {"code": "EXP", "name": "Operating Expenses", "parent_code": None, "account_type": "operating_expense", "is_assignable": False, "is_pnl": False},
    {"code": "EXP-REPAIRS", "name": "Repairs & Maintenance", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    {"code": "EXP-UTILITIES", "name": "Utilities", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    {"code": "EXP-MGMT", "name": "Property Management Fees", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    {"code": "EXP-HOA", "name": "HOA Fees", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    {"code": "EXP-INS", "name": "Insurance", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    {"code": "EXP-TAX", "name": "Property Taxes", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    {"code": "EXP-PROF", "name": "Legal & Professional", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    {"code": "EXP-ADV", "name": "Advertising", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    {"code": "EXP-TRAVEL", "name": "Travel & Transportation", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    {"code": "EXP-BANK", "name": "Bank Fees", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    {"code": "EXP-OTHER", "name": "Other Expense", "parent_code": "EXP", "account_type": "operating_expense", "is_assignable": True, "is_pnl": True},
    
    # Property Costs
    {"code": "PRP", "name": "Property Costs", "parent_code": None, "account_type": "property_cost", "is_assignable": False, "is_pnl": False},
    {"code": "INT-MORTGAGE", "name": "Mortgage Interest", "parent_code": "PRP", "account_type": "property_cost", "is_assignable": True, "is_pnl": True},
    {"code": "CAP-IMP", "name": "Capital Improvements", "parent_code": "PRP", "account_type": "property_cost", "is_assignable": True, "is_pnl": True},
    
    # Capital Accounts
    {"code": "CAP", "name": "Capital Accounts", "parent_code": None, "account_type": "capital_non_expense", "is_assignable": False, "is_pnl": False},
    {"code": "CAP-PRIN", "name": "Principal Reduction", "parent_code": "CAP", "account_type": "capital_non_expense", "is_assignable": True, "is_pnl": False},
    {"code": "OWN-DIST", "name": "Owner Distributions", "parent_code": "CAP", "account_type": "capital_non_expense", "is_assignable": True, "is_pnl": False},
    {"code": "OWN-CONT", "name": "Owner Contributions", "parent_code": "CAP", "account_type": "capital_non_expense", "is_assignable": True, "is_pnl": False},
    
    # Transfers
    {"code": "TRN", "name": "Transfers", "parent_code": None, "account_type": "transfer", "is_assignable": False, "is_pnl": False},
    {"code": "TRN-INT", "name": "Internal Transfer", "parent_code": "TRN", "account_type": "transfer", "is_assignable": True, "is_pnl": False},
]

async def seed_chart():
    async with AsyncSessionLocal() as session:
        # First pass: insert accounts (parents first usually, but we can do it in two passes or use a recursive logic)
        # Here we'll just insert them one by one.
        for acct in CHART_OF_ACCOUNTS:
            # Note: The actual table might use different column names. 
            # The plan says "Each leaf has a stable code (e.g., INC-RENT)".
            # I'll assume the table is 'accounts'.
            await session.execute(text("""
                INSERT INTO accounts (code, name, parent_code, account_type, is_assignable, is_pnl)
                VALUES (:code, :name, :parent_code, :account_type, :is_assignable, :is_pnl)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    parent_code = EXCLUDED.parent_code,
                    account_type = EXCLUDED.account_type,
                    is_assignable = EXCLUDED.is_assignable,
                    is_pnl = EXCLUDED.is_pnl
            """), acct)
        await session.commit()
    print("Chart of accounts seeded.")

if __name__ == "__main__":
    asyncio.run(seed_chart())
