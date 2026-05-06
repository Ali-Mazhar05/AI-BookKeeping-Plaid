from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import structlog
from sqlalchemy import text

from zalazar.db import engine, AsyncSessionLocal
from zalazar.plaid.sync import sync_account

logger = structlog.get_logger()

async def plaid_daily_sync():
    async with AsyncSessionLocal() as session:
        # 1. Start job_run
        result = await session.execute(
            text("""
                INSERT INTO job_runs (job_name, status)
                VALUES ('plaid_daily_sync', 'running')
                RETURNING id
            """)
        )
        run_id = result.scalar_one()
        await session.commit()

        try:
            # 2. Fetch active accounts
            accounts_result = await session.execute(
                text("SELECT id FROM bank_accounts WHERE is_active = TRUE")
            )
            accounts = accounts_result.fetchall()

            for account in accounts:
                logger.info("Running daily sync for account", account_id=account.id)
                await sync_account(account.id)
            
            # 3. Finish job_run
            await session.execute(
                text("UPDATE job_runs SET status = 'success', ended_at = NOW() WHERE id = :run_id"),
                {"run_id": run_id}
            )
            await session.commit()
            
        except Exception as e:
            logger.error("Daily sync failed", error=str(e))
            await session.execute(
                text("UPDATE job_runs SET status = 'failed', error_message = :error, ended_at = NOW() WHERE id = :run_id"),
                {"run_id": run_id, "error": str(e)}
            )
            await session.commit()
            raise

async def reconcile_daily():
    from zalazar.reconciler import reconcile_account
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                INSERT INTO job_runs (job_name, status)
                VALUES ('reconcile_daily', 'running')
                RETURNING id
            """)
        )
        run_id = result.scalar_one()
        await session.commit()

        try:
            accounts_result = await session.execute(
                text("SELECT id FROM bank_accounts WHERE is_active = TRUE")
            )
            accounts = accounts_result.fetchall()

            for account in accounts:
                logger.info("Running daily reconciliation for account", account_id=account.id)
                await reconcile_account(session, account.id)
            
            await session.execute(
                text("UPDATE job_runs SET status = 'success', ended_at = NOW() WHERE id = :run_id"),
                {"run_id": run_id}
            )
            await session.commit()
            
        except Exception as e:
            logger.error("Daily reconciliation failed", error=str(e))
            await session.execute(
                text("UPDATE job_runs SET status = 'failed', error_message = :error, ended_at = NOW() WHERE id = :run_id"),
                {"run_id": run_id, "error": str(e)}
            )
            await session.commit()
            raise

async def refresh_monthly_pnl():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                INSERT INTO job_runs (job_name, status)
                VALUES ('refresh_monthly_pnl', 'running')
                RETURNING id
            """)
        )
        run_id = result.scalar_one()
        await session.commit()

        try:
            logger.info("Running monthly P&L refresh")
            await session.execute(text("SELECT refresh_monthly_pnl()"))
            
            await session.execute(
                text("UPDATE job_runs SET status = 'success', ended_at = NOW() WHERE id = :run_id"),
                {"run_id": run_id}
            )
            await session.commit()
            
        except Exception as e:
            logger.error("Monthly P&L refresh failed", error=str(e))
            await session.execute(
                text("UPDATE job_runs SET status = 'failed', error_message = :error, ended_at = NOW() WHERE id = :run_id"),
                {"run_id": run_id, "error": str(e)}
            )
            await session.commit()
            raise

