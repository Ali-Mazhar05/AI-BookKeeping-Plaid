import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def track():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text('SELECT transaction_date, amount, description_clean, status FROM transactions ORDER BY created_at DESC'))
        txs = res.fetchall()
        print('Total count:', len(txs))
        print('Total Sum:', sum([r[1] for r in txs]))
        for t in txs:
            print(t[0], t[1], t[2])

if __name__ == "__main__":
    asyncio.run(track())
