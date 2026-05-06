import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'transactions'"))
        columns = [row[0] for row in result.fetchall()]
        print("Columns in transactions table:")
        for col in columns:
            print(f"- {col}")

if __name__ == "__main__":
    asyncio.run(main())
