import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def add():
    async with AsyncSessionLocal() as s:
        # Get Mortgage Interest account ID
        res = await s.execute(text("SELECT id FROM accounts WHERE name = 'Mortgage Interest'"))
        acc_id = res.scalar()
        
        await s.execute(text("""
            INSERT INTO vendor_rules (pattern, account_id, property_attribution, confidence, match_type, source)
            VALUES ('ACH PAYMENT', :acc_id, 'even_split', 0.95, 'contains', 'manual')
        """), {"acc_id": acc_id})
        await s.commit()
        print("Added ACH PAYMENT rule.")

if __name__ == "__main__":
    asyncio.run(add())
