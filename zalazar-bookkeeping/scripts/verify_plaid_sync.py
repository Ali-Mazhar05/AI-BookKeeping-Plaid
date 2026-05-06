import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

async def verify_sync():
    async with AsyncSessionLocal() as session:
        try:
            print("=== PLAID SYNC VERIFICATION REPORT ===")
            
            # 1. Total count
            res = await session.execute(text("SELECT COUNT(*) FROM transactions"))
            total = res.scalar()
            print(f"Total Transactions in DB: {total}")
            
            # 2. Count by bank account
            res = await session.execute(text("""
                SELECT b.bank_name, b.account_name, COUNT(t.id) as count
                FROM bank_accounts b
                LEFT JOIN transactions t ON b.id = t.bank_account_id
                GROUP BY b.bank_name, b.account_name
                ORDER BY count DESC
            """))
            print("\nTransactions per Bank Account:")
            for row in res.fetchall():
                print(f"- {row.bank_name} ({row.account_name}): {row.count}")
                
            # 3. Status breakdown
            res = await session.execute(text("""
                SELECT status, COUNT(*) as count
                FROM transactions
                GROUP BY status
            """))
            print("\nStatus Breakdown:")
            for row in res.fetchall():
                print(f"- {row.status}: {row.count}")
                
            # 4. Metadata check
            res = await session.execute(text("""
                SELECT COUNT(*) FROM transactions 
                WHERE merchant_name IS NOT NULL OR plaid_category_primary IS NOT NULL
            """))
            meta_count = res.scalar()
            print(f"\nTransactions with Plaid Metadata: {meta_count}")
            
            print("\n" + "="*40)
            
        except Exception as e:
            print(f"Error during verification: {e}")

if __name__ == "__main__":
    asyncio.run(verify_sync())
