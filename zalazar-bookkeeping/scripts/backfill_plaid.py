import asyncio
import structlog
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
from zalazar.plaid.sync import sync_account

logger = structlog.get_logger()

async def run_backfill():
    async with AsyncSessionLocal() as session:
        # Get job_runs run id
        result = await session.execute(
            text("""
                INSERT INTO job_runs (job_name, status)
                VALUES ('backfill_plaid', 'running')
                RETURNING id
            """)
        )
        run_id = result.scalar_one()
        await session.commit()
        
        try:
            # For each bank_accounts row with plaid_cursor IS NULL
            accounts_result = await session.execute(
                text("""
                    SELECT id 
                    FROM bank_accounts 
                    WHERE plaid_cursor IS NULL AND is_active = TRUE
                """)
            )
            accounts = accounts_result.fetchall()
            
            for account in accounts:
                logger.info("Starting backfill for account", account_id=account.id)
                await sync_account(account.id)
                
            # Finish job
            await session.execute(
                text("UPDATE job_runs SET status = 'success', ended_at = NOW() WHERE id = :run_id"),
                {"run_id": run_id}
            )
            await session.commit()
            logger.info("Backfill completed successfully.")
            
        except Exception as e:
            logger.error("Backfill failed", error=str(e))
            await session.execute(
                text("UPDATE job_runs SET status = 'failed', error_message = :error, ended_at = NOW() WHERE id = :run_id"),
                {"run_id": run_id, "error": str(e)}
            )
            await session.commit()
            raise

if __name__ == "__main__":
    asyncio.run(run_backfill())
