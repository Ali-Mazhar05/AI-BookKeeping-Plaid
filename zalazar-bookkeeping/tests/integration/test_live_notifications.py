"""
Notification Matrix — Live Integration Tests
Maps to todo_notifications.md § 2 Notification Matrix (8 rows).

Sends REAL SMS to SMS_RECIPIENT and REAL email to EMAIL_RECIPIENT from .env.
DB is stubbed; only the transport layer (RingCentral / SMTP) is live.

Run:
    python -m pytest tests/integration/test_live_notifications.py -v -s

LEGEND in test docstrings:
  [IMPLEMENTED]  — trigger exists in production code today
  [GAP]          — plan requires this but code does not fire it yet
"""
import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

ENTITY_ID = uuid4()




def _db():
    """Minimal AsyncSession stub — no real DB required."""
    session = AsyncMock()
    row = MagicMock()
    row.scalar_one.return_value = uuid4()
    row.scalar.return_value = 0       # throttle count = 0  → not throttled
    row.fetchone.return_value = None  # no per-entity notification settings
    session.execute.return_value = row
    return session


def _dispatch_ctx():
    """Common patches for dispatch internals so only the transport is real."""
    return (
        patch("zalazar.notifier.dispatch.get_notification_settings",
              new_callable=AsyncMock, return_value=None),
        patch("zalazar.notifier.dispatch._is_throttled",
              new_callable=AsyncMock, return_value=False),
    )


async def _fire(notification_type, channel, context):
    """Helper: run _send_impl with real transport and stubbed DB."""
    from zalazar.notifier import dispatch
    with _dispatch_ctx()[0], _dispatch_ctx()[1]:
        await dispatch._send_impl(
            _db(), ENTITY_ID,
            notification_type=notification_type,
            channel=channel,
            context=context,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Row 1 — Large Expense
# Trigger:  Expense > large_expense_threshold (default $1,000)
# Channel:  SMS  (immediate)
# Status:   [IMPLEMENTED] in plaid/sync.py — fires when amount < -1000
# Template: large_expense.jinja2  →  "${{ amount }} at {{ vendor }}"
# ─────────────────────────────────────────────────────────────────────────────
async def test_large_expense():
    """$1,250 charge at Home Depot crosses the $1,000 threshold → SMS."""
    today = date.today().isoformat()
    await _fire(
        notification_type="large_expense",
        channel="sms",
        context={
            "amount": "1,250.00",
            "vendor": "Home Depot",
            "date": today,
            "dashboard_url": "http://localhost:5173/review?tx_id=test-001",
        },
    )
    print("\n  [Row 1] large_expense SMS sent — check +19737552608")


# ─────────────────────────────────────────────────────────────────────────────
# Row 2 — Income Received
# Trigger:  Transaction classified as type='income'
# Channel:  SMS  (immediate)
# Status:   [GAP] template exists but no dispatch.send call in sync.py yet
# Template: income_received.jinja2  →  "${{ amount }} from {{ source }}"
# ─────────────────────────────────────────────────────────────────────────────
async def test_income_received():
    """Rent payment from Tenant A classified as income → SMS. [GAP: trigger not wired]"""
    today = date.today().isoformat()
    await _fire(
        notification_type="income_received",
        channel="sms",
        context={
            "amount": "2,000.00",
            "source": "Tenant A — Unit 3B",
            "date": today,
            "dashboard_url": "http://localhost:5173",
        },
    )
    print("\n  [Row 2] income_received SMS sent — check +19737552608")


# ─────────────────────────────────────────────────────────────────────────────
# Row 3 — Review Required
# Trigger:  Transactions in flagged / ai_suggested state
# Channel:  SMS  (daily 9 AM digest)
# Status:   [GAP] no daily scheduled job; per-transaction 'uncategorized' fires
#           but does not batch into a count-based digest
# Template: uncategorized.jinja2  →  "{{ count }} transactions waiting"
# ─────────────────────────────────────────────────────────────────────────────
async def test_review_required():
    """7 transactions stuck in review queue trigger daily digest SMS. [GAP: no daily job]"""
    await _fire(
        notification_type="uncategorized",
        channel="sms",
        context={
            "count": 7,
            "dashboard_url": "http://localhost:5173/review",
        },
    )
    print("\n  [Row 3] review_required (uncategorized) SMS sent — check +19737552608")


# ─────────────────────────────────────────────────────────────────────────────
# Row 4 — Reconciliation Mismatch
# Trigger:  Plaid balance ≠ system calculated balance (tolerance $0.01)
# Channel:  Both  (immediate)
# Status:   [IMPLEMENTED] in reconciler.py
# Template: reconciliation_mismatch.jinja2 + .html.jinja2
# ─────────────────────────────────────────────────────────────────────────────
async def test_reconciliation_mismatch():
    """$250 discrepancy on Chase Business Checking → SMS + Email."""
    await _fire(
        notification_type="reconciliation_mismatch",
        channel="both",
        context={
            "diff": "250.00",
            "amount": "250.00",
            "account": "Chase Business Checking",
            "plaid_balance": "12,750.00",
            "calculated_balance": "12,500.00",
            "dashboard_url": "http://localhost:5173/reconciliation",
        },
    )
    print("\n  [Row 4] reconciliation_mismatch SMS+Email sent")


# ─────────────────────────────────────────────────────────────────────────────
# Row 5 — Cash Flow Change
# Trigger:  Significant MTD Δ% vs prior period (threshold: cash_flow_change_pct)
# Channel:  SMS  (daily 7:45 AM)
# Status:   [GAP] template exists but no daily job and no dispatch.send call
# Template: cash_flow_change.jinja2  →  "change of {{ delta }} for {{ period }}"
# ─────────────────────────────────────────────────────────────────────────────
async def test_cash_flow_change():
    """MTD expenses down 35% vs April → daily SMS alert. [GAP: no scheduler job]"""
    await _fire(
        notification_type="cash_flow_change",
        channel="sms",
        context={
            "delta": "-35.0%",
            "period": "May 2026",
            "dashboard_url": "http://localhost:5173/cashflow",
        },
    )
    print("\n  [Row 5] cash_flow_change SMS sent — check +19737552608")


# ─────────────────────────────────────────────────────────────────────────────
# Row 6a — Plaid Auth Alert: ITEM_LOGIN_REQUIRED
# Trigger:  Plaid webhook ITEM_LOGIN_REQUIRED
# Channel:  Both  (immediate)
# Status:   [IMPLEMENTED] in plaid/webhooks.py — but uses 'reconciliation_mismatch'
#           type. Plan calls for a dedicated 'plaid_auth_alert' type (future work).
# ─────────────────────────────────────────────────────────────────────────────
async def test_plaid_auth_alert_login_required():
    """Chase re-authentication required → SMS + Email via webhook handler."""
    from uuid import uuid4 as _uuid4
    from zalazar.plaid.webhooks import handle_webhook

    account_row = MagicMock()
    account_row.id = _uuid4()
    account_row.entity_id = ENTITY_ID
    account_row.bank_name = "Chase"
    account_row.account_name = "Business Checking"

    session = _db()
    session.execute.return_value.fetchone.return_value = account_row

    with patch("zalazar.plaid.webhooks.client", MagicMock()), \
         patch("zalazar.plaid.webhooks.dispatch") as mock_dispatch:

        from zalazar.notifier import dispatch as real_dispatch
        # Let the real dispatch run (real transport), only stub the DB internals
        async def _real_send(**kwargs):
            kwargs.pop("session", None)  # webhooks passes session=; we supply our own stub
            with _dispatch_ctx()[0], _dispatch_ctx()[1]:
                await real_dispatch._send_impl(_db(), **kwargs)

        mock_dispatch.send = _real_send
        mock_dispatch.get_dashboard_url.return_value = "http://localhost:5173/"

        await handle_webhook(session, {
            "webhook_type": "TRANSACTIONS",
            "webhook_code": "ITEM_LOGIN_REQUIRED",
            "item_id": "plaid_item_test_001",
        })

    print("\n  [Row 6a] plaid_auth_alert LOGIN_REQUIRED SMS+Email sent")


# ─────────────────────────────────────────────────────────────────────────────
# Row 6b — Plaid Auth Alert: PENDING_EXPIRATION
# Trigger:  Plaid webhook PENDING_EXPIRATION
# Channel:  Both  (immediate)
# Status:   [GAP] webhooks.py has a logger.warning but no dispatch.send call
# ─────────────────────────────────────────────────────────────────────────────
async def test_plaid_auth_alert_pending_expiration():
    """Chase token expiring in 7 days → Email only via PENDING_EXPIRATION webhook."""
    await _fire(
        notification_type="plaid_auth_alert",
        channel="email",
        context={
            "account": "Chase – Business Checking",
            "reauth_url": "http://localhost:5173/reconnect?item_id=plaid_item_test_001",
        },
    )
    print("\n  [Row 6b] plaid_auth_alert PENDING_EXPIRATION Email sent")


# ─────────────────────────────────────────────────────────────────────────────
# Row 7 — Nightly Sync Status: Success
# Trigger:  plaid_daily_sync job completes successfully
# Channel:  Email  (nightly, post-sync)
# Status:   [GAP] jobs.py has no dispatch.send call after sync loop
#           No 'nightly_sync_status' template exists yet
# ─────────────────────────────────────────────────────────────────────────────
async def test_nightly_sync_status_success():
    """Sync completed: 3 accounts, 47 new transactions → Email."""
    await _fire(
        notification_type="nightly_sync_status",
        channel="email",
        context={
            "success": True,
            "synced_count": 3,
            "error_count": 0,
            "errors": [],
            "dashboard_url": "http://localhost:5173",
        },
    )
    print("\n  [Row 7a] nightly_sync SUCCESS Email sent")


# ─────────────────────────────────────────────────────────────────────────────
# Row 7b — Nightly Sync Status: Failure
# Trigger:  plaid_daily_sync job raises an exception
# Channel:  Email  (immediate on failure)
# Status:   [GAP] same as above — no dispatch.send in except block of jobs.py
# ─────────────────────────────────────────────────────────────────────────────
async def test_nightly_sync_status_failure():
    """Sync failed with connection timeout → Email to admin."""
    await _fire(
        notification_type="nightly_sync_status",
        channel="email",
        context={
            "success": False,
            "synced_count": 0,
            "error_count": 1,
            "errors": ["Account abc123: Connection timeout after 30s"],
            "dashboard_url": "http://localhost:5173",
        },
    )
    print("\n  [Row 7b] nightly_sync FAILURE Email sent")


# ─────────────────────────────────────────────────────────────────────────────
# Row 8 — Weekly Summary
# Trigger:  APScheduler job, Monday 6:00 AM
# Channel:  Email  (scheduled)
# Status:   [IMPLEMENTED] in scheduler.py — run_weekly_summary()
# Template: weekly_summary.html.jinja2
# ─────────────────────────────────────────────────────────────────────────────
async def test_weekly_summary():
    """Monday morning portfolio snapshot → rich HTML email."""
    await _fire(
        notification_type="weekly_summary",
        channel="email",
        context={
            "income": "8,400.00",
            "expenses": "3,200.00",
            "net_flow": "5,200.00",
            "count": 42,
            "pending_count": 3,
            "dashboard_url": "http://localhost:5173",
            "end_date": date.today().isoformat(),
        },
    )
    print("\n  [Row 8] weekly_summary Email sent — check alimazhar3005@gmail.com")
