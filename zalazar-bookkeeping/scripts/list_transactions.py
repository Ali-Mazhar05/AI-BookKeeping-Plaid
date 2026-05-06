import asyncio
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT vendor_name_clean, status, categorization_reason FROM transactions"))
        rows = res.fetchall()
        if not rows:
            print("No transactions found.")
        for row in rows:
            print(f"Vendor: {row[0]}, Status: {row[1]}, Reason: {row[2]}")

if __name__ == "__main__":
    asyncio.run(check())
