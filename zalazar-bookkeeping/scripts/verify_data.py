import asyncio
import sys
from pathlib import Path

# Add src to sys.path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def check_data():
    async with AsyncSessionLocal() as session:
        # Check entities
        res = await session.execute(text("SELECT COUNT(*) FROM entities"))
        count = res.scalar()
        print(f"Entities count: {count}")
        
        if count == 0:
            print("Creating a default entity for the dashboard...")
            await session.execute(text("INSERT INTO entities (name, type) VALUES ('Juan Zalazar Holdings', 'llc')"))
            await session.commit()
            print("Default entity created.")

        # Check transactions
        res = await session.execute(text("SELECT COUNT(*) FROM transactions"))
        tx_count = res.scalar()
        print(f"Transactions count: {tx_count}")

if __name__ == "__main__":
    asyncio.run(check_data())
