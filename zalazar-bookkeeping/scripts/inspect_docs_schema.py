import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'source_documents'"))
        for row in res:
            print(f"{row[0]}: {row[1]}")

if __name__ == "__main__":
    asyncio.run(check())
