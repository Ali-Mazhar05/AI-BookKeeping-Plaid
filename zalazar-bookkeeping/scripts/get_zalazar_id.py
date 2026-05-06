import asyncio
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def get_id():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT id FROM entities WHERE name = 'Zalazar Holdings' LIMIT 1"))
        row = res.fetchone()
        if row:
            print(row[0])
        else:
            print("Not Found")

if __name__ == "__main__":
    asyncio.run(get_id())
