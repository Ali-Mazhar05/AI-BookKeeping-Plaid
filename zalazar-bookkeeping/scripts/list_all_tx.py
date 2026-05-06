import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as s:
        res = await s.execute(text("SELECT id, description_clean, status, entity_id FROM transactions"))
        rows = res.fetchall()
        print(f"Total Transactions: {len(rows)}")
        for r in rows:
            print(f"{r.id}: {r.description_clean} ({r.status}) [Entity: {r.entity_id}]")

if __name__ == "__main__":
    asyncio.run(check())
