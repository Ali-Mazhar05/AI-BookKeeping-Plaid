import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal

async def list_constraints():
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(text("""
                SELECT conname, pg_get_constraintdef(oid) 
                FROM pg_constraint 
                WHERE conrelid = 'transaction_allocations'::regclass
            """))
            for row in res.fetchall():
                print(f"{row[0]}: {row[1]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_constraints())
