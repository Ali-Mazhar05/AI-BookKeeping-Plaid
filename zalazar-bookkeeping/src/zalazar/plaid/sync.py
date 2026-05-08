from typing import Optional
from decimal import Decimal
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from .client import get_plaid_client, decrypt_token
from ..db import AsyncSessionLocal, pg_advisory_lock
import structlog
from ..normalizer import clean_vendor, infer_type
from ..classifier import classify_transaction
from ..allocator import allocate
from ..notifier import dispatch
import asyncio

logger = structlog.get_logger()
client = get_plaid_client()

async def sync_account(account_id: str):
    """
    Syncs Plaid transactions for a single account and runs them through the pipeline.
    Expects account_id to refer to `bank_accounts.id`.
    """
    async with AsyncSessionLocal() as session:
        # Fetch account details and cursor
        result = await session.execute(
            text("""
                SELECT id, entity_id, plaid_item_id, plaid_access_token_encrypted, plaid_cursor, account_name, bank_name
                FROM bank_accounts
                WHERE id = :account_id AND is_active = TRUE
            """),
            {"account_id": account_id}
        )
        account = result.fetchone()
        
        if not account:
            logger.warning("Account not found or inactive", account_id=account_id)
            return

        item_id = account.plaid_item_id
        
        # Use advisory lock to prevent concurrent syncs for the same Plaid item.
        # We use zlib.adler32 for a stable 32-bit integer hash across processes.
        import zlib
        lock_id = zlib.adler32(item_id.encode())
        async with pg_advisory_lock(session, lock_id): 
            try:
                access_token = decrypt_token(account.plaid_access_token_encrypted)
            except Exception as e:
                logger.error("Failed to decrypt access token. The PLAID_TOKEN_FERNET_KEY may have changed or the token is corrupted.", 
                             account_id=account_id, bank_name=account.bank_name)
                # Update the account with an error status so the user knows to re-link
                await session.execute(
                    text("UPDATE bank_accounts SET plaid_last_error = 'DECRYPTION_FAILED', is_active = FALSE WHERE id = :id"),
                    {"id": account_id}
                )
                await session.commit()
                return

            cursor = account.plaid_cursor or ""
            
            has_more = True
            while has_more:
                request = TransactionsSyncRequest(
                    access_token=access_token,
                    cursor=cursor,
                    count=100
                )
                
                try:
                    response = client.transactions_sync(request)
                except Exception as e:
                    logger.error("Plaid sync error", item_id=item_id, error=str(e))
                    raise
                    
                added = response.get('added', [])
                modified = response.get('modified', [])
                removed = response.get('removed', [])
                
                for tx in added:
                    try:
                        await process_transaction(session, account, tx)
                        await session.commit()
                    except Exception as e:
                        await session.rollback()
                        logger.error("Transaction processing error (added)", tx_id=tx['transaction_id'], error=str(e))

                for tx in modified:
                    try:
                        await process_modification(session, account, tx)
                        await session.commit()
                    except Exception as e:
                        await session.rollback()
                        logger.error("Transaction processing error (modified)", tx_id=tx['transaction_id'], error=str(e))

                for tx in removed:
                    try:
                        await process_removal(session, tx['transaction_id'])
                        await session.commit()
                    except Exception as e:
                        await session.rollback()
                        logger.error("Transaction processing error (removed)", tx_id=tx['transaction_id'], error=str(e))
                    
                cursor = response['next_cursor']
                has_more = response['has_more']
                
                # Persist cursor and last_synced_at
                await session.execute(
                    text("UPDATE bank_accounts SET plaid_cursor = :cursor, last_synced_at = NOW() WHERE id = :account_id"),
                    {"cursor": cursor, "account_id": account.id}
                )
                await session.commit()

async def process_transaction(session: AsyncSession, account: dict, plaid_tx: dict):
    # 1. Sign inversion (Plaid positive = outflow/expense)
    amount = -Decimal(str(plaid_tx['amount']))
    
    # 2. Normalization
    vendor_clean = clean_vendor(plaid_tx.get('merchant_name') or plaid_tx.get('name') or "")
    description_clean = plaid_tx.get('name') or ""
    tx_type = infer_type(amount)
    
    # 3. Idempotency check
    check = await session.execute(
        text("SELECT id FROM transactions WHERE plaid_transaction_id = :ptx_id"),
        {"ptx_id": plaid_tx['transaction_id']}
    )
    if check.fetchone():
        return
        
    # 4. Classification & Allocation
    tx_model = {
        "plaid_transaction_id": plaid_tx['transaction_id'],
        "entity_id": account.entity_id,
        "bank_account_id": account.id,
        "transaction_date": plaid_tx['date'],
        "amount": amount,
        "vendor_name_clean": vendor_clean,
        "description_clean": description_clean,
        "account_name": account.bank_name if hasattr(account, 'bank_name') else account.account_name,
        "type": tx_type,
        "merchant_name": plaid_tx.get('merchant_name'),
        "payment_channel": plaid_tx.get('payment_channel'),
        "iso_currency_code": plaid_tx.get('iso_currency_code'),
        "plaid_category_primary": plaid_tx.get('personal_finance_category', {}).get('primary') if plaid_tx.get('personal_finance_category') else None,
        "plaid_category_detailed": plaid_tx.get('personal_finance_category', {}).get('detailed') if plaid_tx.get('personal_finance_category') else None,
        "pending": plaid_tx.get('pending', False)
    }
    
    classification = await classify_transaction(session, tx_model)
    
    # 5. Write transaction
    
    query = text("""
        INSERT INTO transactions (
            entity_id, bank_account_id, plaid_transaction_id, transaction_date, 
            amount, vendor_name_raw, vendor_name_clean, description, description_clean, status, 
            categorization_method, categorization_reason, ai_raw_response, account_id,
            merchant_name, payment_channel, iso_currency_code, 
            plaid_category_primary, plaid_category_detailed, plaid_pending
        ) VALUES (
            :entity_id, :bank_account_id, :plaid_transaction_id, :transaction_date,
            :amount, :vendor_name_raw, :vendor_name_clean, :description, :description_clean, :status,
            :categorization_method, :categorization_reason, :ai_raw_response, :account_id,
            :merchant_name, :payment_channel, :iso_currency_code,
            :plaid_category_primary, :plaid_category_detailed, :pending
        ) RETURNING id
    """)
    
    params = {
        "entity_id": tx_model['entity_id'],
        "bank_account_id": tx_model['bank_account_id'],
        "plaid_transaction_id": tx_model['plaid_transaction_id'],
        "transaction_date": tx_model['transaction_date'],
        "amount": tx_model['amount'],
        "vendor_name_raw": plaid_tx.get('merchant_name') or plaid_tx.get('name'),
        "vendor_name_clean": tx_model['vendor_name_clean'],
        "description": plaid_tx.get('name') or "Plaid Transaction",
        "description_clean": tx_model['description_clean'],
        "status": classification['status'],
        "categorization_method": classification['method'],
        "categorization_reason": classification.get('reason'),
        "ai_raw_response": classification.get('ai_raw'),
        "account_id": classification.get('account_id'),
        "merchant_name": tx_model['merchant_name'],
        "payment_channel": tx_model['payment_channel'],
        "iso_currency_code": tx_model['iso_currency_code'],
        "plaid_category_primary": tx_model['plaid_category_primary'],
        "plaid_category_detailed": tx_model['plaid_category_detailed'],
        "pending": tx_model['pending']
    }
    
    result = await session.execute(query, params)
    tx_id = result.scalar_one()
    
    # Notify when AI cannot confidently categorize — email only; SMS digest fires at 9 AM
    if classification['status'] == 'pending_review':
        asyncio.create_task(
            dispatch.send(
                entity_id=tx_model['entity_id'],
                notification_type='uncategorized',
                channel='email',
                context={
                    "vendor": tx_model['vendor_name_clean'] or tx_model['description_clean'],
                    "amount": f"{abs(amount):,.2f}",
                    "date": str(tx_model['transaction_date']),
                    "dashboard_url": dispatch.get_dashboard_url(f"/review?tx_id={tx_id}"),
                },
                related_transaction_id=tx_id,
            )
        )

    # If auto_categorized, we MUST have allocations
    if classification['status'] == 'auto_categorized':
        allocations = await allocate(session, tx_model, classification)
        for alloc in allocations:
            await session.execute(
                text("""
                    INSERT INTO transaction_allocations (
                        transaction_id, property_id, amount, percentage, method, confidence_property
                    ) VALUES (
                        :transaction_id, :property_id, :amount, :percentage, :method, :confidence
                    )
                """),
                {
                    "transaction_id": tx_id,
                    "property_id": alloc['property_id'],
                    "amount": alloc['amount'],
                    "percentage": alloc.get('percentage'),
                    "method": alloc['method'],
                    "confidence": alloc['confidence']
                }
            )

    # 6. Trigger Notifications (Flow integration)
    if amount < -1000: # Outflow > $1000
        # Fire-and-forget notification so we don't block the sync loop
        asyncio.create_task(
            dispatch.send(
                entity_id=tx_model['entity_id'],
                notification_type='large_expense',
                channel='both',
                context={
                    "amount": f"{abs(amount):,.2f}",
                    "vendor": tx_model['vendor_name_clean'] or tx_model['description_clean'],
                    "date": tx_model['transaction_date'].isoformat() if hasattr(tx_model['transaction_date'], 'isoformat') else str(tx_model['transaction_date']),
                    "dashboard_url": dispatch.get_dashboard_url(f"/review?tx_id={tx_id}")
                },
                related_transaction_id=tx_id
            )
        )

    if amount > 0: # Inflow — income received
        asyncio.create_task(
            dispatch.send(
                entity_id=tx_model['entity_id'],
                notification_type='income_received',
                channel='sms',
                context={
                    "amount": f"{amount:,.2f}",
                    "source": tx_model['vendor_name_clean'] or tx_model['description_clean'],
                    "date": tx_model['transaction_date'].isoformat() if hasattr(tx_model['transaction_date'], 'isoformat') else str(tx_model['transaction_date']),
                    "dashboard_url": dispatch.get_dashboard_url(f"/review?tx_id={tx_id}"),
                },
                related_transaction_id=tx_id,
            )
        )

async def process_modification(session: AsyncSession, account: dict, plaid_tx: dict):
    """Updates an existing transaction with new data from Plaid."""
    amount = -Decimal(str(plaid_tx['amount']))
    vendor_clean = clean_vendor(plaid_tx.get('merchant_name') or plaid_tx.get('name') or "")
    
    # Update core fields. We don't re-classify automatically to avoid overwriting user changes,
    # unless it was previously pending_review.
    query = text("""
        UPDATE transactions 
        SET amount = :amount,
            vendor_name_clean = :vendor_clean,
            description_clean = :description_clean,
            description = :description,
            merchant_name = :merchant_name,
            plaid_category_primary = :primary_cat,
            plaid_category_detailed = :detailed_cat,
            plaid_pending = :pending
        WHERE plaid_transaction_id = :ptx_id
    """)
    
    await session.execute(query, {
        "amount": amount,
        "vendor_clean": vendor_clean,
        "description_clean": plaid_tx.get('name') or "",
        "description": plaid_tx.get('name') or "Plaid Transaction",
        "merchant_name": plaid_tx.get('merchant_name'),
        "primary_cat": plaid_tx.get('personal_finance_category', {}).get('primary') if plaid_tx.get('personal_finance_category') else None,
        "detailed_cat": plaid_tx.get('personal_finance_category', {}).get('detailed') if plaid_tx.get('personal_finance_category') else None,
        "pending": plaid_tx.get('pending', False),
        "ptx_id": plaid_tx['transaction_id']
    })

async def process_removal(session: AsyncSession, plaid_tx_id: str):
    """Marks a transaction as excluded because it was removed from Plaid."""
    await session.execute(
        text("""
            UPDATE transactions 
            SET status = 'excluded', 
                categorization_reason = 'removed_from_plaid' 
            WHERE plaid_transaction_id = :ptx_id
        """),
        {"ptx_id": plaid_tx_id}
    )

async def reclassify_transactions(entity_id: str):
    """Re-classifies every transaction currently in the review queue for the entity."""
    async with AsyncSessionLocal() as session:
        # Fetch all queue-eligible transactions — pending_review, flagged, and ai_suggested
        # Include entity_id and account_name so the classifier has full context
        res = await session.execute(
            text("""
                SELECT
                    t.id, t.entity_id, t.bank_account_id,
                    t.plaid_transaction_id, t.transaction_date, t.amount,
                    t.vendor_name_clean, t.description_clean, t.description,
                    t.merchant_name, t.payment_channel, t.iso_currency_code,
                    t.plaid_category_primary, t.plaid_category_detailed, t.plaid_pending,
                    b.account_name
                FROM transactions t
                LEFT JOIN bank_accounts b ON b.id = t.bank_account_id
                WHERE t.entity_id = :entity_id
                  AND t.status IN ('pending_review', 'flagged', 'ai_suggested')
            """),
            {"entity_id": entity_id},
        )
        txs = res.fetchall()

        logger.info("Starting re-classification", entity_id=entity_id, count=len(txs))

        for tx in txs:
            try:
                tx_model = dict(tx._mapping)
                tx_model['pending'] = tx_model.pop('plaid_pending')

                classification = await classify_transaction(session, tx_model)

                await session.execute(
                    text("""
                        UPDATE transactions
                        SET status                = :status,
                            categorization_method = :method,
                            categorization_reason = :reason,
                            ai_raw_response       = CAST(:ai_raw AS jsonb),
                            account_id            = :account_id,
                            confidence_category   = :confidence,
                            updated_at            = NOW()
                        WHERE id = :id
                    """),
                    {
                        "id": tx.id,
                        "status":     classification['status'],
                        "method":     classification['method'],
                        "reason":     classification.get('reason'),
                        "ai_raw":     json.dumps(classification.get('ai_raw')) if classification.get('ai_raw') else None,
                        "account_id": classification.get('account_id'),
                        "confidence": classification.get('confidence'),
                    },
                )
                
                # Handle allocations if auto-categorized
                if classification['status'] == 'auto_categorized':
                    # Clear existing (just in case)
                    await session.execute(text("DELETE FROM transaction_allocations WHERE transaction_id = :tid"), {"tid": tx.id})
                    
                    allocations = await allocate(session, tx_model, classification)
                    for alloc in allocations:
                        await session.execute(
                            text("""
                                INSERT INTO transaction_allocations (
                                    transaction_id, property_id, amount, percentage, method, confidence_property
                                ) VALUES (
                                    :transaction_id, :property_id, :amount, :percentage, :method, :confidence
                                )
                            """),
                            {
                                "transaction_id": tx.id,
                                "property_id": alloc['property_id'],
                                "amount": alloc['amount'],
                                "percentage": alloc.get('percentage'),
                                "method": alloc['method'],
                                "confidence": alloc['confidence']
                            }
                        )
                
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("Failed to reclassify transaction", tx_id=tx.id, error=str(e))
