import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
import sys
from pathlib import Path

async def check_vendor_rules_schema():
    async with AsyncSessionLocal() as session:
        try:
            # Check column names and types
            res = await session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'vendor_rules'
                ORDER BY ordinal_position
            """))
            print("Columns for vendor_rules:")
            for row in res:
                print(f"  {row.column_name} ({row.data_type}) | Nullable: {row.is_nullable} | Default: {row.column_default}")
            
            # Check constraints
            res = await session.execute(text("""
                SELECT conname, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'vendor_rules'::regclass
            """))
            print("\nConstraints for vendor_rules:")
            for row in res:
                print(f"  {row.conname}: {row.pg_get_constraintdef}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_vendor_rules_schema())
