from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

logger = structlog.get_logger()

async def split_mortgage_transaction(
    session: AsyncSession,
    transaction_id: str,
    property_id: str,
    interest: Decimal,
    principal: Decimal,
    escrow: Decimal = Decimal('0.00'),
    loan_account_number: str = None
):
    """
    Splits a mortgage payment into interest, principal, and escrow.
    Milestone 6.3 logic.
    """
    # 1. Fetch original transaction
    res = await session.execute(
        text("SELECT * FROM transactions WHERE id = :id"),
        {"id": transaction_id}
    )
    tx = res.fetchone()
    if not tx:
        raise ValueError(f"Transaction {transaction_id} not found")

    # Verify sum
    if interest + principal + escrow != abs(tx.amount):
        raise ValueError(f"Split sum ({interest + principal + escrow}) does not match transaction amount ({abs(tx.amount)})")

    # 2. Mark original as excluded
    await session.execute(
        text("""
            UPDATE transactions
            SET status = 'excluded',
                categorization_reason = 'Mortgage payment split'
            WHERE id = :id
        """),
        {"id": transaction_id}
    )

    # Helper to insert child tx
    async def insert_child_tx(amount, account_code, desc_suffix):
        # Find account_id for the code
        acc_res = await session.execute(
            text("SELECT id FROM accounts WHERE code = :code"),
            {"code": account_code}
        )
        account_id = acc_res.scalar_one()

        # Insert transaction
        child_res = await session.execute(
            text("""
                INSERT INTO transactions (
                    entity_id, bank_account_id, transaction_date, amount,
                    vendor_name_clean, description_clean, account_id, status,
                    categorization_method, categorization_reason
                ) VALUES (
                    :entity_id, :bank_id, :date, :amount,
                    :vendor, :desc, :account_id, 'reviewed',
                    'manual_split', 'Mortgage ' || :suffix
                ) RETURNING id
            """),
            {
                "entity_id": tx.entity_id,
                "bank_id": tx.bank_account_id,
                "date": tx.transaction_date,
                "amount": -amount, # Outflow
                "vendor": tx.vendor_name_clean,
                "desc": (tx.description_clean or "") + " [" + desc_suffix + "]",
                "account_id": account_id,
                "suffix": desc_suffix
            }
        )
        child_id = child_res.scalar_one()

        # Insert allocation
        await session.execute(
            text("""
                INSERT INTO transaction_allocations (transaction_id, property_id, amount, method)
                VALUES (:tx_id, :prop_id, :amount, 'direct')
            """),
            {
                "tx_id": child_id,
                "prop_id": property_id,
                "amount": -amount,
                "method": "direct"
            }
        )
        return child_id

    # 3. Create children
    if interest > 0:
        await insert_child_tx(interest, 'INT-MORTGAGE', 'Interest')
    
    if principal > 0:
        await insert_child_tx(principal, 'CAP-PRIN', 'Principal')

    # 4. Create escrow movement if applicable
    if escrow > 0:
        await session.execute(
            text("""
                INSERT INTO escrow_movements (
                    entity_id, property_id, movement_date, movement_type, amount, loan_account_number
                ) VALUES (
                    :entity_id, :property_id, :date, 'contribution', :amount, :loan_acc
                )
            """),
            {
                "entity_id": tx.entity_id,
                "property_id": property_id,
                "date": tx.transaction_date,
                "amount": escrow,
                "loan_acc": loan_account_number
            }
        )

    await session.commit()
    logger.info("Mortgage split complete", transaction_id=transaction_id)
