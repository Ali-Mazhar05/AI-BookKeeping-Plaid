import asyncio
import sys
import os
from uuid import UUID

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text
from zalazar.reconciler import reconcile_account

async def main():
    entity_id = '665c4049-085d-4f32-b2c7-22bd89668e20'
    async with AsyncSessionLocal() as session:
        # 1. Find an active bank account
        res = await session.execute(text("SELECT id FROM bank_accounts WHERE entity_id = :eid AND is_active = TRUE LIMIT 1"), {"eid": entity_id})
        account = res.fetchone()
        if not account:
            print("No active bank account found.")
            return
        
        account_id = str(account[0])
        print(f"Triggering reconciliation for account: {account_id}")
        
        # 2. Reconcile
        try:
            await reconcile_account(session, account_id)
            await session.commit()
            print("Reconciliation complete.")
        except Exception as e:
            print(f"Error during reconciliation: {e}")

if __name__ == "__main__":
    asyncio.run(main())
