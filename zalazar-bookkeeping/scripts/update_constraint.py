import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal

async def update_constraint():
    async with AsyncSessionLocal() as session:
        try:
            print("Updating constraint...")
            await session.execute(text("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_categorization_method_check"))
            await session.execute(text("""
                ALTER TABLE transactions 
                ADD CONSTRAINT transactions_categorization_method_check 
                CHECK (categorization_method IN (
                    'rule', 'ai', 'manual', 'import', 'transfer_logic', 
                    'manual_approval', 'manual_exclusion', 'transfer_detection', 'none'
                ))
            """))
            await session.commit()
            print("SUCCESS")
        except Exception as e:
            print(f"FAILED: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(update_constraint())
