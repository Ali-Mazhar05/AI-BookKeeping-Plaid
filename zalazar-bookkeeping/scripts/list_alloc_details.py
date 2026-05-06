import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as s:
        res = await s.execute(text("""
            SELECT t.description_clean, p.name, ta.amount 
            FROM transaction_allocations ta 
            JOIN transactions t ON ta.transaction_id = t.id 
            JOIN properties p ON ta.property_id = p.id
        """))
        for r in res.fetchall():
            print(f"{r.description_clean} -> {r.name}: {r.amount}")

if __name__ == "__main__":
    asyncio.run(check())
