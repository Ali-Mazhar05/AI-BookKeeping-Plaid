import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def update_constraint():
    async with AsyncSessionLocal() as session:
        try:
            print("Updating source_documents_parse_status_check constraint...")
            await session.execute(text("ALTER TABLE source_documents DROP CONSTRAINT source_documents_parse_status_check"))
            await session.execute(text("""
                ALTER TABLE source_documents 
                ADD CONSTRAINT source_documents_parse_status_check 
                CHECK (parse_status = ANY (ARRAY['pending'::text, 'processing'::text, 'success'::text, 'failed'::text, 'partial'::text]))
            """))
            await session.commit()
            print("Constraint updated successfully.")
        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(update_constraint())
