import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        # Check columns
        res = await session.execute(text("SELECT * FROM notification_settings LIMIT 1"))
        print(f"Columns: {res.keys()}")
        
        # Enable all for the test
        await session.execute(text("UPDATE notification_settings SET notify_large_expense = TRUE, notify_uncategorized = TRUE, notify_income_received = TRUE, notify_cash_flow_change = TRUE, notify_reconciliation_fail = TRUE"))
        await session.commit()
        print("Enabled all notifications in database.")

if __name__ == "__main__":
    asyncio.run(main())
