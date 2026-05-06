import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

async def check_cursors():
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(text("SELECT bank_name, account_name, plaid_cursor FROM bank_accounts WHERE plaid_cursor IS NOT NULL AND plaid_cursor != ''"))
            for row in res.fetchall():
                print(f"{row.bank_name} ({row.account_name}): {row.plaid_cursor}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_cursors())
