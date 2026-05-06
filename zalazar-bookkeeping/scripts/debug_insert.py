import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
import sys
from pathlib import Path
from decimal import Decimal
import datetime
import uuid

sys.path.append(str(Path(__file__).parent.parent / "src"))

async def debug_insert():
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text("""
                    INSERT INTO transactions (
                        entity_id, bank_account_id, plaid_transaction_id, transaction_date, 
                        amount, vendor_name_clean, description_clean, status, 
                        categorization_method, categorization_reason, ai_raw_response, account_id,
                        merchant_name, payment_channel, iso_currency_code, 
                        plaid_category_primary, plaid_category_detailed, plaid_pending
                    ) VALUES (
                        :entity_id, :bank_account_id, :plaid_transaction_id, :transaction_date,
                        :amount, :vendor_name_clean, :description_clean, :status,
                        :categorization_method, :categorization_reason, :ai_raw_response, :account_id,
                        :merchant_name, :payment_channel, :iso_currency_code,
                        :plaid_category_primary, :plaid_category_detailed, :pending
                    )
                """),
                {
                    "entity_id": uuid.UUID('a0000000-0000-0000-0000-000000000001'),
                    "bank_account_id": uuid.UUID('6b120291-1526-4f40-a60e-33041897a6f9'),
                    "plaid_transaction_id": 'rpd6KbDkWJfvndVNexRlcjnoxNpmX9F7qb9Pv',
                    "transaction_date": datetime.date(2026, 4, 14),
                    "amount": Decimal('-5.4'),
                    "vendor_name_clean": 'Uber',
                    "description_clean": 'Uber 063015 SF**POOL**',
                    "description": 'Uber 063015 SF**POOL**',
                    "status": 'pending_review',
                    "categorization_method": 'ai_exhausted',
                    "categorization_reason": 'AI Quota Exhausted: Flagged for manual review',
                    "ai_raw_response": None,
                    "account_id": None,
                    "merchant_name": 'Uber',
                    "payment_channel": 'online',
                    "iso_currency_code": 'USD',
                    "plaid_category_primary": 'TRANSPORTATION',
                    "plaid_category_detailed": 'TRANSPORTATION_TAXIS_AND_RIDE_SHARES',
                    "pending": False
                }
            )
            await session.commit()
            print("SUCCESS")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(debug_insert())
