import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text
from zalazar.allocator import allocate

async def approve():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("""
            SELECT id, entity_id, amount, vendor_name_clean, description_clean, transaction_date, account_id, ai_raw_response 
            FROM transactions 
            WHERE status = 'ai_suggested'
        """))
        for r in res.fetchall():
            tx = dict(r._mapping)
            # Check if it already has property_id from AI
            ai_data = tx.get('ai_raw_response')
            property_id = None
            if ai_data:
                import json
                if isinstance(ai_data, str):
                    ai_data = json.loads(ai_data)
            if property_id:
                # Direct allocation
                await session.execute(
                    text("INSERT INTO transaction_allocations (transaction_id, property_id, amount, method, confidence_property) VALUES (:tid, :pid, :amt, 'direct', 1.0)"),
                    {"tid": tx['id'], "pid": property_id, "amt": tx['amount']}
                )
            else:
                # Use even split for Zalazar
                classification = {'status': 'auto_categorized', 'method': 'ai', 'account_id': tx['account_id'], 'rule': {'property_attribution': 'even_split'}}
                allocations = await allocate(session, tx, classification)
                if not allocations:
                     print(f"Warning: No allocations for tx {tx['id']}")
                for alloc in allocations:
                    await session.execute(
                        text("INSERT INTO transaction_allocations (transaction_id, property_id, amount, percentage, method, confidence_property) VALUES (:tid, :pid, :amt, :pct, :meth, :conf)"),
                        {"tid": tx['id'], "pid": alloc['property_id'], "amt": alloc['amount'], "pct": alloc.get('percentage'), "meth": alloc['method'], "conf": alloc['confidence']}
                    )

            
            await session.execute(text("UPDATE transactions SET status = 'reviewed' WHERE id = :tid"), {"tid": tx['id']})
            
        await session.commit()
        print("Approved transactions and created allocations.")

if __name__ == "__main__":
    asyncio.run(approve())
