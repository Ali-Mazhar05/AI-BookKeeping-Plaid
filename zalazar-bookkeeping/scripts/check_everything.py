import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as s:
        res = await s.execute(text("SELECT status, COUNT(*) as count FROM transactions GROUP BY status"))
        for r in res.fetchall():
            print(f"{r.status}: {r.count}")
        
        res = await s.execute(text("SELECT COUNT(*) FROM transaction_allocations"))
        print(f"Total Allocations: {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
