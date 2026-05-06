import asyncio
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT id, status, categorization_method FROM transactions WHERE status = 'excluded'"))
        rows = res.fetchall()
        print(f"Excluded transactions: {len(rows)}")
        for r in rows:
            print(f"  {r.id}: {r.status} ({r.categorization_method})")

if __name__ == "__main__":
    asyncio.run(check())
