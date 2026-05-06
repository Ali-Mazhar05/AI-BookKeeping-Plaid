import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        try:
            # PostgreSQL command to add value to enum
            # Note: ALTER TYPE ... ADD VALUE cannot run inside a transaction block in some PG versions/drivers
            # but we can try it.
            await session.execute(text("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'weekly_summary'"))
            await session.commit()
            print("Added 'weekly_summary' to notification_type enum.")
        except Exception as e:
            print(f"Error adding to enum: {e}")

if __name__ == "__main__":
    asyncio.run(main())
