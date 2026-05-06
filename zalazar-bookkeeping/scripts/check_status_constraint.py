import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal

async def check_status_constraint():
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(text("""
                SELECT pg_get_constraintdef(oid) 
                FROM pg_constraint 
                WHERE conname = 'transactions_status_check'
            """))
            print(f"Status Constraint Definition: {res.scalar()}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_status_constraint())
