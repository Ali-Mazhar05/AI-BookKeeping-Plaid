from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import timedelta
import structlog

logger = structlog.get_logger()

async def find_transfer_pairs(session: AsyncSession, entity_id: str, window_days: int = 2):
    """
    For each uncategorized transaction, look for an opposite-sign same-magnitude
    transaction on a different bank_account_id of the same entity within window_days.
    If found: pair them, mark both `excluded`, set paired_transaction_id mutually.
    """
    # 1. Fetch uncategorized transactions for the entity
    query = """
        SELECT id, bank_account_id, transaction_date, amount
        FROM transactions
        WHERE entity_id = :entity_id
          AND status IN ('pending_review', 'ai_suggested', 'flagged')
          AND paired_transaction_id IS NULL
    """
    result = await session.execute(text(query), {"entity_id": entity_id})
    transactions = result.fetchall()

    for tx in transactions:
        # 2. Look for opposite-sign, same-magnitude transaction
        # within window_days and on a DIFFERENT bank account
        match_query = """
            SELECT id
            FROM transactions
            WHERE entity_id = :entity_id
              AND bank_account_id != :bank_account_id
              AND amount = :opposite_amount
              AND transaction_date BETWEEN :start_date AND :end_date
              AND paired_transaction_id IS NULL
        """
        
        start_date = tx.transaction_date - timedelta(days=window_days)
        end_date = tx.transaction_date + timedelta(days=window_days)
        
        match_result = await session.execute(text(match_query), {
            "entity_id": entity_id,
            "bank_account_id": tx.bank_account_id,
            "opposite_amount": -tx.amount,
            "start_date": start_date,
            "end_date": end_date
        })
        
        matches = match_result.fetchall()
        
        # 3. Only pair if exactly ONE match is found (avoid ambiguity)
        if len(matches) == 1:
            match_id = matches[0].id
            
            logger.info("Found transfer pair", tx1=tx.id, tx2=match_id, amount=tx.amount)
            
            # Update both transactions
            update_query = """
                UPDATE transactions
                SET status = 'excluded',
                    paired_transaction_id = :paired_id,
                    categorization_method = 'transfer_detection',
                    categorization_reason = 'Matched with opposite transaction ' || :paired_id
                WHERE id = :id
            """
            
            await session.execute(text(update_query), {"id": tx.id, "paired_id": match_id})
            await session.execute(text(update_query), {"id": match_id, "paired_id": tx.id})
            
    await session.commit()
