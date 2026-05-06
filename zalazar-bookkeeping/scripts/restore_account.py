import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def create():
    async with AsyncSessionLocal() as s:
        res = await s.execute(text("SELECT id FROM entities WHERE name = 'Zalazar Holdings'"))
        eid = res.scalar()
        if not eid:
            print("Entity not found")
            return
        await s.execute(
            text("INSERT INTO bank_accounts (entity_id, bank_name, account_name, account_last4, source_type) VALUES (:eid, 'Lima One Capital', 'Operating Account', '1234', 'manual_entry')"),
            {"eid": eid}
        )
        await s.commit()
        print("Account created for Zalazar Holdings")

if __name__ == "__main__":
    asyncio.run(create())
