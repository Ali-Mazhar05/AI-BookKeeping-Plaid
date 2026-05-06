import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
import sys
from pathlib import Path

async def apply_custom_migration(file_path):
    with open(file_path, 'r') as f:
        sql = f.read()
    
    print(f"Applying migration: {file_path}")
    async with AsyncSessionLocal() as session:
        try:
            # Simple split by BEGIN/COMMIT blocks or just run as-is if driver supports it
            # asyncpg prefers individual statements
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            for stmt in statements:
                if stmt.upper() in ('BEGIN', 'COMMIT', 'ROLLBACK'): continue
                print(f"Executing: {stmt[:50]}...")
                await session.execute(text(stmt))
            await session.commit()
            print("SUCCESS: Migration applied.")
        except Exception as e:
            print(f"FAILED: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(apply_custom_migration(sys.argv[1]))
