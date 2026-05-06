import asyncio
import sys
import os

# Add src to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from sqlalchemy import text
from zalazar.db import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as session:
        # Check transactions table
        result = await session.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'transactions' ORDER BY ordinal_position"
        ))
        print("=== transactions table columns ===")
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]}")
        
        # Check if there are transactions in review states
        result = await session.execute(text(
            "SELECT status, COUNT(*) FROM transactions GROUP BY status"
        ))
        print("\n=== Transaction counts by status ===")
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # Check bank_accounts table 
        result = await session.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'bank_accounts' ORDER BY ordinal_position"
        ))
        print("\n=== bank_accounts table columns ===")
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # Check entities table
        result = await session.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'entities' ORDER BY ordinal_position"
        ))
        print("\n=== entities table columns ===")
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]}")
            
        # Check if there are any entities
        result = await session.execute(text("SELECT COUNT(*) FROM entities"))
        count = result.scalar()
        print(f"\nTotal entities: {count}")

asyncio.run(check())
