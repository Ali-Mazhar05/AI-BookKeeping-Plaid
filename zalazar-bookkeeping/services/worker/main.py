import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
# In a real setup, you might configure a SQLAlchemyJobStore here to persist jobs across restarts.
# For simplicity and given the jobs are idempotent, we use the default memory store for now.
# We persist run status in our own job_runs table.

from .jobs import plaid_daily_sync, reconcile_daily, refresh_monthly_pnl
# Import other jobs as they are implemented
# from .jobs import weekly_summary, notifications_rtx

logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.INFO)

async def start_scheduler():
    scheduler = AsyncIOScheduler()
    
    # Plaid daily sync: hour=6, minute=0 local time
    scheduler.add_job(
        plaid_daily_sync,
        'cron',
        hour=6,
        minute=0,
        id='plaid_daily_sync',
        coalesce=True,
        max_instances=1
    )
    
    # Reconciliation: hour=7, minute=0 local time
    scheduler.add_job(
        reconcile_daily,
        'cron',
        hour=7,
        minute=0,
        id='reconcile_daily',
        coalesce=True,
        max_instances=1
    )
    
    # Monthly P&L refresh: hour=7, minute=30 local time
    scheduler.add_job(
        refresh_monthly_pnl,
        'cron',
        hour=7,
        minute=30,
        id='refresh_monthly_pnl',
        coalesce=True,
        max_instances=1
    )
    
    # Add other jobs here once implemented

    
    scheduler.start()
    
    # Keep the main thread alive
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    asyncio.run(start_scheduler())
