import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal

async def check_source_documents_schema():
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'source_documents'
            """))
            for row in res.fetchall():
                print(f"{row[0]}: {row[1]} (Nullable: {row[2]})")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_source_documents_schema())
