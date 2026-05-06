import asyncio
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'accounts'"))
        for row in res:
            print(row[0])

if __name__ == "__main__":
    asyncio.run(check())
