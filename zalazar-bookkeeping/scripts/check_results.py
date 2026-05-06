import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as s:
        print("Source Documents Status:")
        res = await s.execute(text("SELECT filename, parse_status, transaction_count, parse_error FROM source_documents"))
        for r in res.fetchall():
            print(f"{r[0][:30]:30} | {r[1]:10} | {r[2] if r[2] is not None else 'N/A':>3} | {r[3]}")

        res = await s.execute(text("SELECT status, count(*) FROM transactions GROUP BY status"))
        for r in res.fetchall():
            print(f"{r[0]}: {r[1]}")
            
        print("\nTop 10 Transactions:")
        res = await s.execute(text("""
            SELECT t.transaction_date, t.description, t.amount, a.name as account_name, t.status
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.id
            ORDER BY t.transaction_date DESC
            LIMIT 10
        """))
        for r in res.fetchall():
            print(f"{r[0]} | {r[1][:30]:30} | {r[2]:>10} | {r[3] if r[3] else 'None':15} | {r[4]}")


if __name__ == "__main__":
    asyncio.run(check())
