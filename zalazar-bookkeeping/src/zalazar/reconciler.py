from decimal import Decimal
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from zalazar.plaid.client import get_plaid_client, decrypt_token
from plaid.model.accounts_get_request import AccountsGetRequest
from .notifier import dispatch

logger = structlog.get_logger()
client = get_plaid_client()

async def reconcile_account(session: AsyncSession, account_id: str):
    """
    Daily reconciliation job. Compares Plaid balance with our calculated DB balance.
    """
    # 1. Fetch account details
    result = await session.execute(
        text("SELECT * FROM bank_accounts WHERE id = :id AND is_active = TRUE"),
        {"id": account_id}
    )
    account = result.fetchone()
    if not account:
        logger.warning("Account not found or inactive for reconciliation", account_id=account_id)
        return

    # 2. Fetch Plaid balance
    plaid_balance = None
    if account.plaid_access_token_encrypted:
        try:
            access_token = decrypt_token(account.plaid_access_token_encrypted)
            request = AccountsGetRequest(access_token=access_token)
            response = client.accounts_get(request)
            plaid_account = next((a for a in response['accounts'] if a.account_id == account.plaid_account_id), None)
            if plaid_account:
                plaid_balance = Decimal(str(plaid_account.balances.current))
        except Exception as e:
            logger.error("Failed to fetch Plaid balance", error=str(e))
    
    if plaid_balance is None:
        # Fallback to manually entered current_balance if available
        plaid_balance = account.current_balance or Decimal('0.00')
        logger.info("Using DB current_balance for reconciliation fallback", account_id=account_id)
    
    # 3. Calculate DB balance
    calc_result = await session.execute(
        text("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE bank_account_id = :id
              AND status IN ('auto_categorized', 'reviewed', 'excluded')
        """),
        {"id": account_id}
    )
    tx_sum = calc_result.scalar() or Decimal('0.00')
    
    opening_balance = account.opening_balance or Decimal('0.00')
    
    # One-time opening balance back-solve if missing
    if opening_balance == Decimal('0.00') and tx_sum != Decimal('0.00'):
        opening_balance = plaid_balance - tx_sum
        await session.execute(
            text("UPDATE bank_accounts SET opening_balance = :ob WHERE id = :id"),
            {"ob": opening_balance, "id": account_id}
        )
        logger.info("Back-solved opening balance", account_id=account_id, opening_balance=opening_balance)
        
    calculated_balance = opening_balance + tx_sum
    
    # 4. Compare
    diff = plaid_balance - calculated_balance
    tolerance = Decimal('0.01') 
    
    status = 'matched' if abs(diff) <= tolerance else 'flagged'
    
    # 5. Insert reconciliation log
    log_res = await session.execute(
        text("""
            INSERT INTO reconciliation_log (
                reconciliation_date, bank_account_id, entity_id,
                plaid_balance, calculated_balance, difference, status
            ) VALUES (
                :date, :account_id, :entity_id, :plaid_bal, :calc_bal, :diff, :status
            ) RETURNING id
        """),
        {
            "date": date.today(),
            "account_id": account_id,
            "entity_id": account.entity_id,
            "plaid_bal": plaid_balance,
            "calc_bal": calculated_balance,
            "diff": diff,
            "status": status
        }
    )
    recon_id = log_res.scalar_one()
    
    if status == 'flagged':
        logger.warning("Reconciliation mismatch", account_id=account_id, diff=diff)
        try:
            await dispatch.send(
                entity_id=account.entity_id,
                notification_type='reconciliation_mismatch',
                channel='both',
                context={
                    "amount": str(abs(diff)),
                    "diff": f"{diff:,.2f}",
                    "account": account.account_name,
                    "plaid_balance": f"{plaid_balance:,.2f}",
                    "calculated_balance": f"{calculated_balance:,.2f}",
                    "dashboard_url": dispatch.get_dashboard_url(f"/reconciliation?id={recon_id}")
                },
                related_reconciliation_id=recon_id,
                session=session
            )
        except Exception as e:
            logger.error("Failed to send reconciliation notification", error=str(e))
        
    await session.commit()
    logger.info("Reconciliation complete", account_id=account_id, status=status)
