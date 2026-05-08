"""
Live notification test suite.
Queries real database records for each notification type instead of hardcoded values.
Run:  python scripts/test_all_notifications_manual.py
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from sqlalchemy import text
from zalazar.db import AsyncSessionLocal
from zalazar.notifier import dispatch


async def _clear_throttle(session, entity_id, ntype):
    """Remove any existing throttle log so the test notification always fires."""
    await session.execute(
        text("""
            DELETE FROM notification_log
            WHERE entity_id = :eid AND notification_type = :type
        """),
        {"eid": entity_id, "type": ntype},
    )
    await session.commit()


async def _send(session, entity_id, ntype, channel, context, **kwargs):
    print(f"\n  Sending '{ntype}' via {channel}...")
    try:
        await _clear_throttle(session, entity_id, ntype)
        await dispatch.send(
            entity_id=entity_id,
            notification_type=ntype,
            channel=channel,
            context=context,
            session=session,
            **kwargs,
        )
        await session.commit()
        print(f"  OK: {ntype}")
    except Exception as e:
        print(f"  FAILED: {ntype} — {e}")
        import traceback
        traceback.print_exc()
        await session.rollback()


async def run_tests():
    print("=== LIVE NOTIFICATION TEST SUITE ===\n")

    async with AsyncSessionLocal() as session:
        # ── Resolve entity ────────────────────────────────────────────────
        ent_res = await session.execute(text("SELECT id, name FROM entities LIMIT 1"))
        entity = ent_res.fetchone()
        if not entity:
            print("ERROR: No entities found in database. Seed data first.")
            return
        ENTITY_ID = entity.id
        print(f"Entity: {entity.name} ({ENTITY_ID})")

        now = datetime.now()
        pending_count = 0  # set below, reused for weekly_summary

        # ── 1. Large Expense ───────────────────────────────────────────────
        tx_res = await session.execute(
            text("""
                SELECT id, amount, vendor_name_clean, description_clean, transaction_date
                FROM transactions
                WHERE entity_id = :eid AND amount < -1000 AND status != 'excluded'
                ORDER BY transaction_date DESC LIMIT 1
            """),
            {"eid": ENTITY_ID},
        )
        tx = tx_res.fetchone()
        if tx:
            await _send(session, ENTITY_ID, "large_expense", "both", {
                "amount": f"{abs(tx.amount):,.2f}",
                "vendor": tx.vendor_name_clean or tx.description_clean or "Unknown vendor",
                "date": str(tx.transaction_date),
                "dashboard_url": dispatch.get_dashboard_url(f"/review?tx_id={tx.id}"),
            })
        else:
            print("\n  SKIP: large_expense — no transaction with amount < -$1,000 in DB")

        # ── 2. Income Received ─────────────────────────────────────────────
        inc_res = await session.execute(
            text("""
                SELECT id, amount, vendor_name_clean, description_clean, transaction_date
                FROM transactions
                WHERE entity_id = :eid AND amount > 0 AND status != 'excluded'
                ORDER BY transaction_date DESC LIMIT 1
            """),
            {"eid": ENTITY_ID},
        )
        inc_tx = inc_res.fetchone()
        if inc_tx:
            await _send(session, ENTITY_ID, "income_received", "sms", {
                "amount": f"{inc_tx.amount:,.2f}",
                "source": inc_tx.vendor_name_clean or inc_tx.description_clean or "Unknown source",
                "date": str(inc_tx.transaction_date),
                "dashboard_url": dispatch.get_dashboard_url(f"/review?tx_id={inc_tx.id}"),
            })
        else:
            print("\n  SKIP: income_received — no inflow transaction in DB")

        # ── 3. Reconciliation Mismatch ─────────────────────────────────────
        recon_res = await session.execute(
            text("""
                SELECT r.id, r.plaid_balance, r.calculated_balance,
                       (r.plaid_balance - r.calculated_balance) AS diff,
                       b.account_name
                FROM reconciliation_log r
                JOIN bank_accounts b ON b.id = r.bank_account_id
                WHERE b.entity_id = :eid
                  AND ABS(r.plaid_balance - r.calculated_balance) > 0.01
                ORDER BY r.created_at DESC LIMIT 1
            """),
            {"eid": ENTITY_ID},
        )
        recon = recon_res.fetchone()
        if recon:
            await _send(session, ENTITY_ID, "reconciliation_mismatch", "both", {
                "diff": f"{abs(recon.diff):,.2f}",
                "account": recon.account_name,
                "plaid_balance": f"{recon.plaid_balance:,.2f}",
                "calculated_balance": f"{recon.calculated_balance:,.2f}",
                "dashboard_url": dispatch.get_dashboard_url(f"/reconciliation?id={recon.id}"),
            }, related_reconciliation_id=recon.id)
        else:
            print("\n  SKIP: reconciliation_mismatch — no mismatch record in DB")

        # ── 4. Uncategorized Review Digest ─────────────────────────────────
        pend_res = await session.execute(
            text("""
                SELECT COUNT(*) FROM transactions
                WHERE entity_id = :eid
                  AND status IN ('pending_review', 'ai_suggested', 'flagged')
            """),
            {"eid": ENTITY_ID},
        )
        pending_count = pend_res.scalar() or 0
        if pending_count > 0:
            await _send(session, ENTITY_ID, "uncategorized", "sms", {
                "count": pending_count,
                "dashboard_url": dispatch.get_dashboard_url("/review"),
            })
        else:
            print("\n  SKIP: uncategorized — no pending transactions in DB")

        # ── 5. Cash Flow Change ────────────────────────────────────────────
        week_start = (now - timedelta(days=7)).date()
        prev_week_start = (now - timedelta(days=14)).date()

        this_res = await session.execute(
            text("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions
                WHERE entity_id = :eid AND transaction_date >= :start
                  AND status != 'excluded'
            """),
            {"eid": ENTITY_ID, "start": week_start},
        )
        this_week = this_res.scalar() or Decimal("0")

        prev_res = await session.execute(
            text("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions
                WHERE entity_id = :eid
                  AND transaction_date >= :start AND transaction_date < :end
                  AND status != 'excluded'
            """),
            {"eid": ENTITY_ID, "start": prev_week_start, "end": week_start},
        )
        prev_week = prev_res.scalar() or Decimal("0")

        if prev_week != 0:
            change_pct = float((this_week - prev_week) / abs(prev_week) * 100)
            direction = "increase" if change_pct > 0 else "decrease"
            await _send(session, ENTITY_ID, "cash_flow_change", "both", {
                "delta": f"{change_pct:+.1f}% {direction} vs last week",
                "period": now.strftime("%B %Y"),
                "this_week": f"{this_week:,.2f}",
                "prev_week": f"{prev_week:,.2f}",
                "dashboard_url": dispatch.get_dashboard_url("/"),
            })
        else:
            print("\n  SKIP: cash_flow_change — no prior-week data in DB")

        # ── 6. Weekly Summary ──────────────────────────────────────────────
        seven_days_ago = (now - timedelta(days=7)).date()

        exp_res = await session.execute(
            text("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions
                WHERE entity_id = :eid AND amount < 0
                  AND transaction_date >= :dt AND status != 'excluded'
            """),
            {"eid": ENTITY_ID, "dt": seven_days_ago},
        )
        expenses = exp_res.scalar() or Decimal("0")

        inc_sum_res = await session.execute(
            text("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions
                WHERE entity_id = :eid AND amount > 0
                  AND transaction_date >= :dt AND status != 'excluded'
            """),
            {"eid": ENTITY_ID, "dt": seven_days_ago},
        )
        income_sum = inc_sum_res.scalar() or Decimal("0")

        cnt_res = await session.execute(
            text("""
                SELECT COUNT(*) FROM transactions
                WHERE entity_id = :eid
                  AND status IN ('reviewed', 'auto_categorized')
                  AND transaction_date >= :dt
            """),
            {"eid": ENTITY_ID, "dt": seven_days_ago},
        )
        reviewed_count = cnt_res.scalar() or 0

        await _send(session, ENTITY_ID, "weekly_summary", "email", {
            "expenses": f"{abs(expenses):,.2f}",
            "income": f"{income_sum:,.2f}",
            "net_flow": f"{float(income_sum + expenses):,.2f}",
            "count": reviewed_count,
            "pending_count": pending_count,
            "dashboard_url": dispatch.get_dashboard_url("/"),
        })

        # ── 7. Plaid Auth Alert ────────────────────────────────────────────
        acct_res = await session.execute(
            text("""
                SELECT id, bank_name, account_name, plaid_item_id
                FROM bank_accounts
                WHERE entity_id = :eid LIMIT 1
            """),
            {"eid": ENTITY_ID},
        )
        acct = acct_res.fetchone()
        if acct:
            item_id = acct.plaid_item_id or "unknown"
            await _send(session, ENTITY_ID, "plaid_auth_alert", "both", {
                "account": f"{acct.bank_name} – {acct.account_name}",
                "reauth_url": dispatch.get_dashboard_url(f"/reconnect?item_id={item_id}"),
            })
        else:
            print("\n  SKIP: plaid_auth_alert — no bank account found in DB")

    print("\n=== Test Suite Finished ===")


if __name__ == "__main__":
    asyncio.run(run_tests())
