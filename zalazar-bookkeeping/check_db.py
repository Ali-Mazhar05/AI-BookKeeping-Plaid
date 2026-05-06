import asyncio
import json
import os
import sys

# Add project root to sys path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def get_txs():
    async with AsyncSessionLocal() as session:
        query = """
        SELECT t.transaction_date, t.amount, t.description_clean, t.status, 
               t.vendor_name_clean, a.bank_name, a.account_name, t.account_id
        FROM transactions t
        LEFT JOIN bank_accounts a ON a.id = t.bank_account_id
        ORDER BY t.created_at DESC LIMIT 20
        """
        res = await session.execute(text(query))
        txs = [dict(r._mapping) for r in res.fetchall()]
        print(json.dumps(txs, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(get_txs())
