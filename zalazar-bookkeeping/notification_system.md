# Notification System

## Overview

Every notification follows the same path:

```
Trigger (sync / webhook / scheduler)
    → dispatch.send()
    → notification_log INSERT
    → sms.send() and/or email.send()
    → notification_log UPDATE (status = sent | failed | suppressed)
```

The dispatcher (`src/zalazar/notifier/dispatch.py`) handles:
- Per-entity opt-in checks (`notification_settings` table)
- Throttling (max 1 per hour for high-frequency types)
- Jinja2 template rendering (text + HTML)
- Logging every attempt to `notification_log`

---

## Notification Types at a Glance

| Type | Channel | Trigger | Time |
|---|---|---|---|
| `large_expense` | SMS + Email | Transaction sync — outflow > $1,000 | Real-time |
| `income_received` | SMS | Transaction sync — any inflow | Real-time |
| `uncategorized` | Email | Transaction sync — AI can't categorize | Real-time |
| `uncategorized` | SMS | Scheduler — daily digest | 9:00 AM daily |
| `reconciliation_mismatch` | SMS + Email | Reconciler — balance mismatch | 4:30 AM daily |
| `cash_flow_change` | SMS + Email | Scheduler — >20% week-over-week swing | 7:45 AM daily |
| `weekly_summary` | SMS + Email | Scheduler — Monday morning | 5:00 AM Monday |
| `plaid_auth_alert` | SMS + Email | Webhook — login required / permission revoked | Real-time |
| `plaid_auth_alert` | Email | Webhook — token expiring soon | Real-time |
| `nightly_sync_status` | Email | Scheduler — after nightly sync completes | ~4:00 AM daily |

---

## Scheduled Jobs (APScheduler)

All jobs are registered in `src/zalazar/scheduler.py` and run on the server's local time.

### 4:00 AM — Nightly Sync
**Job:** `run_nightly_sync`

Pulls the latest transactions from Plaid for every active bank account. During this run, real-time notifications can fire for each transaction processed (see Real-Time Triggers below). After all accounts finish, a single `nightly_sync_status` email is sent to the admin reporting how many accounts synced and whether any errors occurred.

### 4:30 AM — Daily Reconciliation
**Job:** `run_daily_reconciliation`

Compares the Plaid-reported balance against the sum of all transactions in the database for each account. If a mismatch is found, a `reconciliation_mismatch` notification fires via both SMS and email.

Code: `src/zalazar/reconciler.py` → `reconcile_account()`

### 5:00 AM Monday — Weekly Summary
**Job:** `run_weekly_summary`

Aggregates the last 7 days of income, expenses, and pending transactions for each entity and sends a `weekly_summary` via SMS and email. Only fires on Mondays.

### 7:45 AM — Cash Flow Check
**Job:** `run_cash_flow_check`

Compares net cash flow for the past 7 days against the 7 days before that. If the change exceeds ±20%, a `cash_flow_change` notification fires via both SMS and email. Skips entities with no previous-week data.

### 9:00 AM — Review Digest
**Job:** `run_review_digest`

Counts transactions in `pending_review`, `ai_suggested`, or `flagged` status for each entity. If any exist, sends a single `uncategorized` SMS with the count and a link to the review queue. Skips entities with nothing pending. This is the only SMS for uncategorized transactions — individual transactions during sync send email only to avoid SMS spam.

---

## Real-Time Triggers

These fire immediately during transaction processing or webhook receipt, not on a schedule.

### Large Expense — `src/zalazar/plaid/sync.py`

Fires when a synced transaction is an outflow greater than $1,000 (after Plaid's sign inversion, `amount < -1000`).

- Channel: SMS + Email
- Context: amount, vendor, date, link to review

Throttled: max 1 per hour per entity.

### Income Received — `src/zalazar/plaid/sync.py`

Fires when a synced transaction is an inflow (`amount > 0`).

- Channel: SMS
- Context: amount, source, date, link to review

Throttled: max 1 per hour per entity.

### Uncategorized (per-transaction) — `src/zalazar/plaid/sync.py`

Fires when the AI classifier returns `pending_review` status, meaning it could not confidently categorize the transaction.

- Channel: Email only (the 9 AM SMS digest batches these for SMS)
- Context: vendor, amount, date, link to review queue

Throttled: max 1 per hour per entity.

### Plaid Auth Alert — `src/zalazar/plaid/webhooks.py`

Fires on three Plaid webhook codes:

| Webhook Code | Severity | Channel | What it means |
|---|---|---|---|
| `ITEM_LOGIN_REQUIRED` | Critical | SMS + Email | Bank credentials expired; sync is stopped |
| `USER_PERMISSION_REVOKED` | Critical | SMS + Email | User revoked Plaid access; sync is stopped |
| `PENDING_EXPIRATION` | Warning | Email only | Access token expires within 7 days |

For `ITEM_LOGIN_REQUIRED` and `USER_PERMISSION_REVOKED`, the account is also marked `is_active = FALSE` in `bank_accounts` before the notification fires, so no further syncs attempt until the user re-links.

The notification includes a direct re-authentication URL (`/reconnect?item_id=...`) pointing to the Plaid Link re-auth flow.

---

## Delivery Pipeline

### 1. `dispatch.send()` — Entry Point

`src/zalazar/notifier/dispatch.py`

Accepts `entity_id` (or `None` for system-level notifications like `nightly_sync_status`), looks up per-entity settings, checks throttling, renders templates, logs the attempt, and delegates to the channel senders.

```
dispatch.send(entity_id, notification_type, channel, context)
```

### 2. Per-Entity Settings Check

Reads `notification_settings` table for the entity. If the row is missing, all types default to enabled. The user can disable individual types (e.g., `notify_large_expense = false`). `weekly_summary` and `nightly_sync_status` are always on and cannot be disabled.

### 3. Throttle Check

For `large_expense`, `uncategorized`, and `cash_flow_change`: if a notification of the same type was sent to the same entity within the past hour, the new one is logged as `suppressed` with reason `throttled` and not dispatched.

### 4. Template Rendering

Templates live in `src/zalazar/notifier/templates/`. Each type has two files:

| File | Used for |
|---|---|
| `{type}.jinja2` | SMS body and email plain-text fallback |
| `{type}.html.jinja2` | Email HTML body (extends `base_email.html.jinja2`) |

If a template file is missing, the dispatcher falls back to a hardcoded string.

### 5. SMS — `src/zalazar/notifier/sms.py`

Uses the RingCentral Python SDK. The SDK platform session is cached at module level (with a thread lock) so re-authentication happens at most once per process lifetime, avoiding the HTTP 429 CMN-301 rate limit that occurs when logging in on every send.

Recipient resolves to: `notification_settings.sms_recipient` → `settings.SMS_RECIPIENT`

### 6. Email — `src/zalazar/notifier/email.py`

Sends via SMTP (Gmail App Password). Builds a `MIMEMultipart` message with both `text/plain` and `text/html` parts when an HTML template exists.

Recipient resolves to: `notification_settings.email_recipient` → `settings.EMAIL_RECIPIENT`

### 7. Logging

Every notification attempt (including suppressed ones) is written to the `notification_log` table with:
- `status`: `sent` | `failed` | `suppressed`
- `provider`: `ringcentral` | `gmail`
- `provider_message_id`: the message ID returned by the provider
- `error`: error message if delivery failed
- Links to related transaction, reconciliation, or property if applicable

---

## Daily Timeline

```
04:00 AM   Nightly sync starts — pulls Plaid transactions
             → large_expense alerts fire in real-time (SMS + Email)
             → income_received alerts fire in real-time (SMS)
             → uncategorized alerts fire in real-time (Email only)
04:00 AM   Nightly sync finishes → nightly_sync_status email to admin

04:30 AM   Daily reconciliation runs
             → reconciliation_mismatch fires if balance drifts (SMS + Email)

05:00 AM   Weekly summary fires (Mondays only, SMS + Email)

07:45 AM   Cash flow check runs
             → cash_flow_change fires if week-over-week swing > 20% (SMS + Email)

09:00 AM   Review digest runs
             → uncategorized SMS fires if any transactions need review

All day    Plaid webhooks received in real-time
             → plaid_auth_alert on ITEM_LOGIN_REQUIRED / USER_PERMISSION_REVOKED (SMS + Email)
             → plaid_auth_alert on PENDING_EXPIRATION (Email only)
```

---

## Key Files

| File | Purpose |
|---|---|
| `src/zalazar/notifier/dispatch.py` | Central dispatcher — settings, throttle, template, log, send |
| `src/zalazar/notifier/sms.py` | RingCentral SMS sender |
| `src/zalazar/notifier/email.py` | SMTP email sender |
| `src/zalazar/notifier/templates/` | Jinja2 templates for all 8 notification types |
| `src/zalazar/scheduler.py` | APScheduler jobs — sync, reconcile, digest, summaries |
| `src/zalazar/plaid/sync.py` | Per-transaction real-time triggers |
| `src/zalazar/plaid/webhooks.py` | Plaid webhook handler — auth alerts |
| `src/zalazar/reconciler.py` | Reconciliation logic — mismatch detection |
| `migrations/v3_1_notifications.sql` | `notification_log` and `notification_settings` tables |
| `migrations/v3_4_notification_types.sql` | Adds `plaid_auth_alert` and `nightly_sync_status` enum values |
