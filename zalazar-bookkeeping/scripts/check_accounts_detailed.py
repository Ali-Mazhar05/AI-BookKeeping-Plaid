import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT id, bank_name, account_name, current_balance, opening_balance FROM bank_accounts WHERE entity_id = '665c4049-085d-4f32-b2c7-22bd89668e20'"))
        for row in res.fetchall():
            print(dict(row._mapping))

if __name__ == "__main__":
    asyncio.run(main())
