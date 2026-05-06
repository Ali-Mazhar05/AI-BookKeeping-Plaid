import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import asyncio
import structlog
from zalazar.db import AsyncSessionLocal
from zalazar.plaid.sync import sync_account
from sqlalchemy import text

logger = structlog.get_logger()

async def run_full_sync():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id, account_name FROM bank_accounts WHERE is_active = TRUE")
        )
        accounts = result.fetchall()
        
        if not accounts:
            print("No active bank accounts found to sync.")
            return

        print(f"Starting sync for {len(accounts)} accounts...")
        
        for acc in accounts:
            print(f"Syncing {acc.account_name} ({acc.id})...")
            try:
                await sync_account(acc.id)
                print(f"SUCCESS: {acc.account_name} synced.")
            except Exception as e:
                print(f"FAILED: {acc.account_name} sync error: {e}")

if __name__ == "__main__":
    asyncio.run(run_full_sync())
