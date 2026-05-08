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
        # 1. Nightly Sync at 04:00 AM
        self.scheduler.add_job(
            self.run_nightly_sync, 
            CronTrigger(hour=4, minute=0),
            name="nightly_sync"
        )
        
        # 2. Daily Reconciliation at 04:30 AM (after sync)
        self.scheduler.add_job(
            self.run_daily_reconciliation, 
            CronTrigger(hour=4, minute=30),
            name="daily_reconciliation"
        )
        
        # 3. Weekly Summary on Monday at 05:00 AM
        self.scheduler.add_job(
            self.run_weekly_summary,
            CronTrigger(day_of_week='mon', hour=5, minute=0),
            name="weekly_summary"
        )

        # 4. Daily Review Digest at 09:00 AM (GAP B — SMS batch for uncategorized)
        self.scheduler.add_job(
            self.run_review_digest,
            CronTrigger(hour=9, minute=0),
            name="review_digest"
        )

        # 5. Daily Cash Flow Check at 07:45 AM (GAP C)
        self.scheduler.add_job(
            self.run_cash_flow_check,
            CronTrigger(hour=7, minute=45),
            name="cash_flow_check"
        )

        self.scheduler.start()
        logger.info("Scheduler started with APScheduler")

    async def run_nightly_sync(self):
        logger.info("Job Started: Nightly Sync")
        synced_count = 0
        errors = []
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                text("SELECT id FROM bank_accounts WHERE is_active = TRUE AND plaid_access_token_encrypted IS NOT NULL")
            )
            accounts = res.fetchall()
            for acc in accounts:
                try:
                    await sync_account(str(acc.id))
                    synced_count += 1
                except Exception as e:
                    errors.append(f"Account {acc.id}: {e}")
                    logger.error("Nightly sync failed for account", account_id=acc.id, error=str(e))

        success = len(errors) == 0
        try:
            await dispatch.send(
                entity_id=None,
                notification_type='nightly_sync_status',
                channel='email',
                context={
                    "success": success,
                    "synced_count": synced_count,
                    "error_count": len(errors),
                    "errors": errors,
                    "dashboard_url": dispatch.get_dashboard_url("/"),
                },
            )
        except Exception as e:
            logger.error("Failed to send nightly sync status notification", error=str(e))


    async def run_daily_reconciliation(self):
        logger.info("Job Started: Daily Reconciliation")
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                text("SELECT id FROM bank_accounts WHERE is_active = TRUE AND plaid_access_token_encrypted IS NOT NULL")
            )
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

    async def run_review_digest(self):
        """Sends a single SMS per entity listing how many transactions need review (GAP B)."""
        logger.info("Job Started: Review Digest")
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT id FROM entities"))
            entities = res.fetchall()

            for entity in entities:
                try:
                    pend_res = await session.execute(
                        text("""
                            SELECT COUNT(*) FROM transactions
                            WHERE entity_id = :eid
                              AND status IN ('pending_review', 'ai_suggested', 'flagged')
                        """),
                        {"eid": entity.id},
                    )
                    pending_count = pend_res.scalar() or 0

                    if pending_count == 0:
                        continue

                    await dispatch.send(
                        entity_id=entity.id,
                        notification_type='uncategorized',
                        channel='sms',
                        context={
                            "count": pending_count,
                            "dashboard_url": dispatch.get_dashboard_url("/review"),
                        },
                        session=session,
                    )
                except Exception as e:
                    logger.error("Review digest failed for entity", entity_id=entity.id, error=str(e))

    async def run_cash_flow_check(self):
        """Compares this week's spend to last week's; notifies on >20% swing (GAP C)."""
        logger.info("Job Started: Cash Flow Check")
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT id FROM entities"))
            entities = res.fetchall()

            now = datetime.now()
            week_start = (now - timedelta(days=7)).date()
            prev_week_start = (now - timedelta(days=14)).date()

            for entity in entities:
                try:
                    this_res = await session.execute(
                        text("""
                            SELECT COALESCE(SUM(amount), 0) FROM transactions
                            WHERE entity_id = :eid
                              AND transaction_date >= :start
                              AND status != 'excluded'
                        """),
                        {"eid": entity.id, "start": week_start},
                    )
                    this_week = this_res.scalar() or Decimal('0')

                    prev_res = await session.execute(
                        text("""
                            SELECT COALESCE(SUM(amount), 0) FROM transactions
                            WHERE entity_id = :eid
                              AND transaction_date >= :start
                              AND transaction_date < :end
                              AND status != 'excluded'
                        """),
                        {"eid": entity.id, "start": prev_week_start, "end": week_start},
                    )
                    prev_week = prev_res.scalar() or Decimal('0')

                    if prev_week == 0:
                        continue

                    change_pct = ((this_week - prev_week) / abs(prev_week)) * 100
                    if abs(change_pct) < 20:
                        continue

                    direction = "increase" if change_pct > 0 else "decrease"
                    await dispatch.send(
                        entity_id=entity.id,
                        notification_type='cash_flow_change',
                        channel='both',
                        context={
                            "delta": f"{change_pct:+.1f}% {direction} vs last week",
                            "period": now.strftime("%B %Y"),
                            "this_week": f"{this_week:,.2f}",
                            "prev_week": f"{prev_week:,.2f}",
                            "dashboard_url": dispatch.get_dashboard_url("/"),
                        },
                        session=session,
                    )
                except Exception as e:
                    logger.error("Cash flow check failed for entity", entity_id=entity.id, error=str(e))

scheduler = Scheduler()
