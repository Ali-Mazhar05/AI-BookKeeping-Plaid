import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT email_recipient FROM notification_settings"))
        rows = result.fetchall()
        print("Notification Recipients:")
        for row in rows:
            print(f"- {row[0]}")

if __name__ == "__main__":
    asyncio.run(main())
