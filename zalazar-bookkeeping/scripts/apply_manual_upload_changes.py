import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal

async def apply_db_changes():
    async with AsyncSessionLocal() as session:
        try:
            print("Adding source_type to bank_accounts...")
            await session.execute(text("ALTER TABLE bank_accounts ADD COLUMN IF NOT EXISTS source_type source_type NOT NULL DEFAULT 'manual_entry'"))
            
            print("Updating existing accounts to 'plaid'...")
            await session.execute(text("UPDATE bank_accounts SET source_type = 'plaid' WHERE plaid_item_id IS NOT NULL"))
            
            print("Allowing NULL plaid_transaction_id in transactions...")
            await session.execute(text("ALTER TABLE transactions ALTER COLUMN plaid_transaction_id DROP NOT NULL"))
            
            await session.commit()
            print("Database changes applied successfully.")
        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(apply_db_changes())
