import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT entity_id, COUNT(*) as count FROM bank_accounts WHERE plaid_access_token_encrypted IS NOT NULL GROUP BY entity_id"))
        for row in res.fetchall():
            print(dict(row._mapping))

if __name__ == "__main__":
    asyncio.run(main())
