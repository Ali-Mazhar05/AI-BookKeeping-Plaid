import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def wipe():
    async with AsyncSessionLocal() as s:
        await s.execute(text("TRUNCATE source_documents CASCADE"))
        await s.commit()
        print("Wiped source_documents")

if __name__ == "__main__":
    asyncio.run(wipe())
