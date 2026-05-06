import asyncio
import sys
import os
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from zalazar.db import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT notification_type, body
            FROM notification_log 
            WHERE notification_type = 'weekly_summary'
            ORDER BY created_at DESC LIMIT 1
        """))
        rows = result.fetchall()
        for row in rows:
            print(f"TYPE: {row[0]}")
            print(f"BODY:\n{row[1]}")

if __name__ == "__main__":
    asyncio.run(main())
