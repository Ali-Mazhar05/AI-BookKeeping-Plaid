from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
from datetime import datetime, timedelta
import structlog
from sqlalchemy import text
from .db import AsyncSessionLocal
from .plaid.sync import sync_account
from .reconciler import reconcile_account
from .notifier import dispatch
from decimal import Decimal

logger = structlog.get_logger()

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    async def start(self):
        # 1. Nightly Sync at 04:50 AM
        self.scheduler.add_job(
            self.run_nightly_sync, 
            CronTrigger(hour=4, minute=50),
            name="nightly_sync"
        )
        
        # 2. Daily Reconciliation at 05:55 AM
        self.scheduler.add_job(
            self.run_daily_reconciliation, 
            CronTrigger(hour=5, minute=55),
            name="daily_reconciliation"
        )
        
        # 3. Weekly Summary on Monday at 05:00 AM
        self.scheduler.add_job(
            self.run_weekly_summary, 
            CronTrigger(day_of_week='mon', hour=5, minute=0),
            name="weekly_summary"
        )
        
        self.scheduler.start()
        logger.info("Scheduler started with APScheduler")

    async def run_nightly_sync(self):
        logger.info("Job Started: Nightly Sync (DISABLED: Plaid logic commented out)")
        # async with AsyncSessionLocal() as session:
        #     res = await session.execute(text("SELECT id FROM bank_accounts WHERE is_active = TRUE"))
        #     accounts = res.fetchall()
        #     for acc in accounts:
        #         try:
        #             await sync_account(str(acc.id))
        #         except Exception as e:
        #             logger.error("Nightly sync failed for account", account_id=acc.id, error=str(e))


    async def run_daily_reconciliation(self):
        logger.info("Job Started: Daily Reconciliation")
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT id FROM bank_accounts WHERE is_active = TRUE"))
            accounts = res.fetchall()
            for acc in accounts:
                try:
                    await reconcile_account(session, str(acc.id))
                except Exception as e:
                    logger.error("Daily reconciliation failed for account", account_id=acc.id, error=str(e))

    async def run_weekly_summary(self):
        logger.info("Job Started: Weekly Summary")
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT id, name FROM entities"))
            entities = res.fetchall()
            
            seven_days_ago = datetime.now() - timedelta(days=7)
            
            for entity in entities:
                try:
                    # Expenses
                    exp_res = await session.execute(
                        text("SELECT SUM(amount) FROM transactions WHERE entity_id = :eid AND amount < 0 AND transaction_date >= :dt AND status != 'excluded'"),
                        {"eid": entity.id, "dt": seven_days_ago.date()}
                    )
                    expenses = exp_res.scalar() or Decimal('0')
                    
                    # Income
                    inc_res = await session.execute(
                        text("SELECT SUM(amount) FROM transactions WHERE entity_id = :eid AND amount > 0 AND transaction_date >= :dt AND status != 'excluded'"),
                        {"eid": entity.id, "dt": seven_days_ago.date()}
                    )
                    income = inc_res.scalar() or Decimal('0')
                    
                    # Count reviewed/auto-categorized in last 7 days
                    count_res = await session.execute(
                        text("SELECT COUNT(*) FROM transactions WHERE entity_id = :eid AND status IN ('reviewed', 'auto_categorized') AND transaction_date >= :dt"),
                        {"eid": entity.id, "dt": seven_days_ago.date()}
                    )
                    count = count_res.scalar() or 0
                    
                    # Count currently pending
                    pend_res = await session.execute(
                        text("SELECT COUNT(*) FROM transactions WHERE entity_id = :eid AND status IN ('pending_review', 'ai_suggested', 'flagged')"),
                        {"eid": entity.id}
                    )
                    pending_count = pend_res.scalar() or 0
                    
                    await dispatch.send(
                        entity_id=entity.id,
                        notification_type='weekly_summary',
                        channel='both',
                        context={
                            "expenses": f"{abs(expenses):,.2f}",
                            "income": f"{income:,.2f}",
                            "net_flow": f"{(income + expenses):,.2f}",
                            "count": count,
                            "pending_count": pending_count,
                            "dashboard_url": dispatch.get_dashboard_url("/")
                        },
                        session=session
                    )
                except Exception as e:
                    logger.error("Weekly summary failed for entity", entity_id=entity.id, error=str(e))

scheduler = Scheduler()
