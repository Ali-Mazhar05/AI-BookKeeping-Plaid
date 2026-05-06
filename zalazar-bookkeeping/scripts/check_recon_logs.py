import asyncio
import sys
import os
from uuid import UUID

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    entity_id = '665c4049-085d-4f32-b2c7-22bd89668e20'
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(text("SELECT * FROM reconciliation_log WHERE entity_id = :eid"), {"eid": entity_id})
            rows = res.fetchall()
            print(f"Found {len(rows)} logs for entity {entity_id}")
            for row in rows:
                print(dict(row._mapping))
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
