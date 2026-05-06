import asyncio
from sqlalchemy import text
from src.zalazar.db import AsyncSessionLocal

async def get_real_data():
    async with AsyncSessionLocal() as session:
        # Get a pending transaction
        tx_res = await session.execute(text("SELECT id, entity_id FROM transactions WHERE status = 'pending_review' LIMIT 1"))
        tx = tx_res.fetchone()
        
        # Get a reconciliation record (if any)
        recon_res = await session.execute(text("SELECT id FROM reconciliation_log LIMIT 1"))
        recon = recon_res.fetchone()
        
        print(f"REAL_TX_ID: {tx[0] if tx else 'NONE'}")
        print(f"REAL_ENTITY_ID: {tx[1] if tx else 'NONE'}")
        print(f"REAL_RECON_ID: {recon[0] if recon else 'NONE'}")

if __name__ == "__main__":
    asyncio.run(get_real_data())
