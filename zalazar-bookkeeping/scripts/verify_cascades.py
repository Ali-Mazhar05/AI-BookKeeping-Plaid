import asyncio
import sys
import os
from uuid import uuid4

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    entity_id = '665c4049-085d-4f32-b2c7-22bd89668e20'
    async with AsyncSessionLocal() as session:
        # 1. Create a dummy bank account
        acc_id = str(uuid4())
        print(f"Creating dummy account: {acc_id}")
        await session.execute(text("""
            INSERT INTO bank_accounts (id, entity_id, bank_name, account_name, is_active)
            VALUES (:id, :eid, 'Test Bank', 'Test Account', TRUE)
        """), {"id": acc_id, "eid": entity_id})
        
        # 2. Add a dummy transaction
        tx_id = str(uuid4())
        print(f"Creating dummy transaction: {tx_id}")
        await session.execute(text("""
            INSERT INTO transactions (id, entity_id, bank_account_id, transaction_date, amount, vendor_name_raw, vendor_name_clean, description, status)
            VALUES (:id, :eid, :aid, '2026-01-01', -100.00, 'Test Vendor Raw', 'Test Vendor', 'Test Description', 'reviewed')
        """), {"id": tx_id, "eid": entity_id, "aid": acc_id})
        
        # 3. Add an allocation
        print("Creating dummy allocation")
        await session.execute(text("""
            INSERT INTO transaction_allocations (transaction_id, property_id, amount, method)
            SELECT :tid, id, -100.00, 'direct' FROM properties WHERE entity_id = :eid LIMIT 1
        """), {"tid": tx_id, "eid": entity_id})
        
        # 4. Add a reconciliation log
        recon_id = str(uuid4())
        print(f"Creating dummy reconciliation log: {recon_id}")
        await session.execute(text("""
            INSERT INTO reconciliation_log (id, reconciliation_date, bank_account_id, entity_id, plaid_balance, calculated_balance, difference, status)
            VALUES (:id, '2026-01-01', :aid, :eid, 0, 0, 0, 'matched')
        """), {"id": recon_id, "aid": acc_id, "eid": entity_id})
        
        await session.commit()
        
        # 5. Verify they exist
        res = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE id = :id"), {"id": tx_id})
        print(f"Transaction exists before delete: {res.scalar() == 1}")
        
        res = await session.execute(text("SELECT COUNT(*) FROM transaction_allocations WHERE transaction_id = :id"), {"id": tx_id})
        print(f"Allocation exists before delete: {res.scalar() == 1}")
        
        # 6. Delete the bank account
        print(f"Deleting bank account: {acc_id}")
        await session.execute(text("DELETE FROM bank_accounts WHERE id = :id"), {"id": acc_id})
        await session.commit()
        
        # 7. Verify cascading deletes
        res = await session.execute(text("SELECT COUNT(*) FROM bank_accounts WHERE id = :id"), {"id": acc_id})
        print(f"Account deleted: {res.scalar() == 0}")
        
        res = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE bank_account_id = :id"), {"id": acc_id})
        print(f"Transactions deleted: {res.scalar() == 0}")
        
        res = await session.execute(text("SELECT COUNT(*) FROM transaction_allocations WHERE transaction_id = :id"), {"id": tx_id})
        print(f"Allocations deleted: {res.scalar() == 0}")
        
        res = await session.execute(text("SELECT COUNT(*) FROM reconciliation_log WHERE bank_account_id = :id"), {"id": acc_id})
        print(f"Reconciliation logs deleted: {res.scalar() == 0}")

if __name__ == "__main__":
    asyncio.run(main())
