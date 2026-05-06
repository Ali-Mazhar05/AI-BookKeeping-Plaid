import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal

async def check_view_def():
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(text("""
                SELECT definition 
                FROM pg_matviews 
                WHERE matviewname = 'monthly_property_pnl'
            """))
            print(f"View Definition: {res.scalar()}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_view_def())
