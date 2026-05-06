import asyncio
from sqlalchemy import text
from src.zalazar.db import AsyncSessionLocal

async def count_pending():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE status IN ('ai_suggested', 'flagged', 'pending_review')"))
        print(f"COUNT: {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(count_pending())
