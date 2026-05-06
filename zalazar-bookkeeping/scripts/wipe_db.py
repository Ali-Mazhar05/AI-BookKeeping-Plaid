import asyncio
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def clear():
    async with AsyncSessionLocal() as session:
        await session.execute(text('DELETE FROM transaction_allocations'))
        await session.execute(text('DELETE FROM transactions'))
        await session.execute(text('DELETE FROM source_documents'))
        await session.execute(text('DELETE FROM bank_accounts'))
        await session.commit()
        print("Database cleared.")

if __name__ == "__main__":
    asyncio.run(clear())
