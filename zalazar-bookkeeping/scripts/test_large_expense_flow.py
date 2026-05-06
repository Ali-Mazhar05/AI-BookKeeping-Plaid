import asyncio
import sys
import os
from datetime import date
from decimal import Decimal
from uuid import UUID

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from zalazar.db import AsyncSessionLocal
from zalazar.plaid.sync import process_transaction
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        # 1. Get a bank account to use
        res = await session.execute(text("SELECT id, entity_id, bank_name, account_name FROM bank_accounts LIMIT 1"))
        account = res.fetchone()
        if not account:
            print("No bank accounts found.")
            return
            
        # 2. Mock a large Plaid transaction ($1,500 outflow)
        # Plaid positive = outflow. In sync.py it is inverted to -1500.
        plaid_tx = {
            "transaction_id": f"large_test_{os.urandom(4).hex()}",
            "amount": 1500.00,
            "name": "TEST LARGE EXPENSE - RENT PAYMENT",
            "merchant_name": "Landlord Services",
            "date": date.fromisoformat('2025-04-25'),
            "pending": False,
            "iso_currency_code": "USD"
        }
        
        print(f"Processing mock large transaction of ${plaid_tx['amount']}...")
        
        # 3. Process it (this should trigger dispatch.send)
        try:
            await process_transaction(session, account, plaid_tx)
            await session.commit()
            print("Successfully processed transaction and triggered notification.")
            print("Check your email for 'Alert: Large Expense'!")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
