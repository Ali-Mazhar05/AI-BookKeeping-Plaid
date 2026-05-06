import asyncio
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def get_acc():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT id, name FROM accounts WHERE name ILIKE '%Transfer%' AND is_assignable = TRUE"))
        for row in res:
            print(f"ID: {row[0]}, Name: {row[1]}")

if __name__ == "__main__":
    asyncio.run(get_acc())
