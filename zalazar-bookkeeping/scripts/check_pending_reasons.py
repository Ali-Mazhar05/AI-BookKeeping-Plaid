import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

async def check_reasons():
    async with AsyncSessionLocal() as session:
        try:
            print("=== PENDING REVIEW REASONS ===")
            res = await session.execute(text("""
                SELECT categorization_reason, COUNT(*) as count
                FROM transactions
                WHERE status = 'pending_review'
                GROUP BY categorization_reason
            """))
            for row in res.fetchall():
                print(f"- {row.categorization_reason}: {row.count}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_reasons())
