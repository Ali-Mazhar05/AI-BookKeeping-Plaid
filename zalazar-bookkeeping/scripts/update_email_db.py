import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        await session.execute(text("UPDATE notification_settings SET email_recipient = 'alimazhar3005@gmail.com'"))
        await session.commit()
        print("Updated notification_settings.email_recipient to alimazhar3005@gmail.com")

if __name__ == "__main__":
    asyncio.run(main())
