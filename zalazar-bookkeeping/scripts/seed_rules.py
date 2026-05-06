import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal

async def seed_rules():
    async with AsyncSessionLocal() as session:
        try:
            # Get account IDs
            res = await session.execute(text("SELECT id, name FROM accounts"))
            accounts = {row.name: row.id for row in res.fetchall()}
            
            # 1. Lima One Capital -> Mortgage Interest (even_split)
            # 2. Insurance -> Insurance (even_split)
            
            rules = [
                {
                    "pattern": "LIMA ONE",
                    "account_id": accounts.get("Mortgage Interest"),
                    "attribution": "even_split",
                    "notes": "Mortgage for Zalazar properties - split evenly"
                },
                {
                    "pattern": "INSURANCE",
                    "account_id": accounts.get("Insurance"),
                    "attribution": "even_split",
                    "notes": "Insurance for Zalazar properties - split evenly"
                }
            ]
            
            for r in rules:
                if r["account_id"]:
                    await session.execute(
                        text("""
                            INSERT INTO vendor_rules (pattern, match_type, account_id, confidence, property_attribution, source, notes)
                            VALUES (:pattern, 'contains', :acc_id, 0.99, :attr, 'manual', :notes)
                        """),
                        {"pattern": r["pattern"], "acc_id": r["account_id"], "attr": r["attribution"], "notes": r["notes"]}
                    )
            
            await session.commit()
            print("Successfully seeded baseline vendor rules.")
        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(seed_rules())
