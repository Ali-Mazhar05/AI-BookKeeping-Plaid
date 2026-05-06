import asyncio
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text('SELECT bank_name, account_last4 FROM bank_accounts WHERE is_active = TRUE'))
        rows = res.fetchall()
        if not rows:
            print("No active bank accounts found.")
        for row in rows:
            print(f"Bank: {row[0]}, Last4: {row[1]}")

if __name__ == "__main__":
    asyncio.run(check())
