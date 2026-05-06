import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

async def check_entities():
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(text("SELECT id FROM entities"))
            ids = [str(r.id) for r in res.fetchall()]
            print(f"Entities: {ids}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_entities())
