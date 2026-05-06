import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def get_cols():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'audit_log'"))
        rows = res.fetchall()
        for r in rows:
            print(r)

if __name__ == "__main__":
    asyncio.run(get_cols())
