import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def get():
    async with AsyncSessionLocal() as s:
        res = await s.execute(text("SELECT id, name FROM entities"))
        for r in res.fetchall():
            print(f"{r.name}: {r.id}")

if __name__ == "__main__":
    asyncio.run(get())
