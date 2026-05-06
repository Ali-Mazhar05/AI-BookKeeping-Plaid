import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

async def check():
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(text("SELECT count(*) FROM transactions"))
            print(f"Total Transactions in DB: {res.scalar()}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
