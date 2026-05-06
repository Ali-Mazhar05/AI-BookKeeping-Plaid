import asyncio
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT id, bank_name, is_active FROM bank_accounts"))
        rows = res.fetchall()
        print(f"Bank accounts: {len(rows)}")
        for r in rows:
            print(f"  {r.id}: {r.bank_name} (active={r.is_active})")

if __name__ == "__main__":
    asyncio.run(check())
