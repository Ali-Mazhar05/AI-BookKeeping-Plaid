import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def get_constraints():
    async with AsyncSessionLocal() as session:
        query = """
        SELECT conname, pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE conname = 'vendor_rules_source_check';
        """
        res = await session.execute(text(query))
        rows = res.fetchall()
        for row in rows:
            print(row)

if __name__ == "__main__":
    asyncio.run(get_constraints())
