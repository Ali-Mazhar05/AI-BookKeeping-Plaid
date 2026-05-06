import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        commands = [
            # 1. transactions -> bank_accounts
            "ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_bank_account_id_fkey",
            "ALTER TABLE transactions ADD CONSTRAINT transactions_bank_account_id_fkey FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE",
            
            # 2. reconciliation_log -> bank_accounts
            "ALTER TABLE reconciliation_log DROP CONSTRAINT IF EXISTS reconciliation_log_bank_account_id_fkey",
            "ALTER TABLE reconciliation_log ADD CONSTRAINT reconciliation_log_bank_account_id_fkey FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE",
            
            # 3. source_documents -> bank_accounts
            "ALTER TABLE source_documents DROP CONSTRAINT IF EXISTS source_documents_bank_account_id_fkey",
            "ALTER TABLE source_documents ADD CONSTRAINT source_documents_bank_account_id_fkey FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE",
            
            # 4. transaction_allocations -> transactions
            "ALTER TABLE transaction_allocations DROP CONSTRAINT IF EXISTS transaction_allocations_transaction_id_fkey",
            "ALTER TABLE transaction_allocations ADD CONSTRAINT transaction_allocations_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE",
            
            # 5. notification_log -> transactions
            "ALTER TABLE notification_log DROP CONSTRAINT IF EXISTS notification_log_related_transaction_id_fkey",
            "ALTER TABLE notification_log ADD CONSTRAINT notification_log_related_transaction_id_fkey FOREIGN KEY (related_transaction_id) REFERENCES transactions(id) ON DELETE CASCADE",
            
            # 6. notification_log -> reconciliation_log
            "ALTER TABLE notification_log DROP CONSTRAINT IF EXISTS notification_log_related_reconciliation_id_fkey",
            "ALTER TABLE notification_log ADD CONSTRAINT notification_log_related_reconciliation_id_fkey FOREIGN KEY (related_reconciliation_id) REFERENCES reconciliation_log(id) ON DELETE CASCADE",
        ]
        
        for cmd in commands:
            print(f"Executing: {cmd}")
            try:
                await session.execute(text(cmd))
                await session.commit()
                print("Success.")
            except Exception as e:
                print(f"Error: {e}")
                await session.rollback()

if __name__ == "__main__":
    asyncio.run(main())
