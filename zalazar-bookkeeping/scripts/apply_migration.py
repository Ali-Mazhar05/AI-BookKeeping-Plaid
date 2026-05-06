import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
import sys
import os
from pathlib import Path

# Add src to sys.path
sys.path.append(str(Path(__file__).parent.parent / "src"))

async def apply_migration():
    migration_file = Path(__file__).parent.parent / "migrations" / "v3_3_plaid_metadata.sql"
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    print(f"Applying migration: {migration_file.name}")
    async with AsyncSessionLocal() as session:
        try:
            # Split by semicolon if needed, but standard text(sql) might work for multiple statements in some drivers
            # asyncpg might require individual statements.
            # We'll split by ; and filter empty
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            for stmt in statements:
                print(f"Executing: {stmt[:50]}...")
                await session.execute(text(stmt))
            await session.commit()
            print("SUCCESS: Migration applied.")
        except Exception as e:
            print(f"FAILED: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(apply_migration())
