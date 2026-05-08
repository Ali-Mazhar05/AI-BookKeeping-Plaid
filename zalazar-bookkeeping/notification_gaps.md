# Notification Gaps — Zalazar Bookkeeping

This document explains every **GAP** surfaced by the integration test suite
(`tests/integration/test_live_notifications.py`).

A **GAP** means: the notification was proved deliverable end-to-end (the SMS or email
arrived during tests), but **the production code never actually fires it** — so in a
live environment the user would never receive it, even when the triggering event occurs.

---

## Quick Summary

| Row | Notification | Channel | Deliverable? | Auto-fires in prod? |
|-----|---|---|---|---|
| 1 | Large Expense | SMS | ✅ | ✅ `sync.py:237` |
| 2 | Income Received | SMS | ✅ | ❌ **GAP A** |
| 3 | Review Required (daily digest) | SMS | ✅ | ❌ **GAP B** |
| 4 | Reconciliation Mismatch | SMS + Email | ✅ | ✅ `reconciler.py:101` |
| 5 | Cash Flow Change | SMS | ✅ | ❌ **GAP C** |
| 6a | Plaid Auth Alert — Login Required | SMS + Email | ✅ | ⚠️ fires as wrong type (**GAP D**) |
| 6b | Plaid Auth Alert — Pending Expiration | SMS + Email | ✅ | ❌ **GAP E** |
| 7 | Nightly Sync Status | Email | ✅ | ❌ **GAP F** |
| 8 | Weekly Summary | Email | ✅ | ✅ `scheduler.py:109` |

---

## GAP A — Income Received: trigger never fires

### What should happen
Every time a Plaid transaction syncs in with a **positive amount** (rent payment,
refund, deposit), an SMS should go out immediately:
> *"Income received: $2,000.00 from Tenant A — Unit 3B on 2026-05-07."*

### What actually happens
`sync.py` only calls `dispatch.send` for two cases:
- `amount < -1000` → `large_expense` (line 237)
- `classification['status'] == 'pending_review'` → `uncategorized` (line 197)

There is **no check for positive amounts**. A $2,000 rent deposit syncs silently.
The `income_received.jinja2` template exists and renders correctly — it is simply
never called.

### What needs to be added
In [plaid/sync.py](src/zalazar/plaid/sync.py) after the `large_expense` block (~line 252), add:

```python
if amount > 0:
    asyncio.create_task(
        dispatch.send(
            entity_id=tx_model['entity_id'],
            notification_type='income_received',
            channel='sms',
            context={
                "amount": f"{amount:,.2f}",
                "source": tx_model['vendor_name_clean'] or tx_model['description_clean'],
                "date": str(tx_model['transaction_date']),
                "dashboard_url": dispatch.get_dashboard_url(f"/review?tx_id={tx_id}"),
            },
            related_transaction_id=tx_id,
        )
    )
```

---

## GAP B — Review Required: no daily digest job

### What should happen
Every day at **9:00 AM**, one SMS should go out summarising how many transactions
are waiting in the review queue:
> *"Action Required: You have 7 transactions waiting for categorization."*

### What actually happens
The `uncategorized` notification fires **immediately, per transaction**, the moment
the AI cannot classify it. If 15 transactions come in overnight you get 15 individual
SMS messages — one per transaction, all within seconds of each other. No digest exists.

The `scheduler.py` runs three jobs: `run_nightly_sync` (04:00), `run_daily_reconciliation`
(04:30), and `run_weekly_summary` (Monday 05:00). There is **no 9 AM review digest job**.

### What needs to be added
**1. New scheduler job in [scheduler.py](src/zalazar/scheduler.py)**

Register the job in `__init__`:
```python
self.scheduler.add_job(
    self.run_review_digest,
    CronTrigger(hour=9, minute=0),
    name="review_digest"
)
```

Add the job method:
```python
async def run_review_digest(self):
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT id FROM entities"))
        for entity in res.fetchall():
            count_res = await session.execute(
                text("""SELECT COUNT(*) FROM transactions
                        WHERE entity_id = :eid
                        AND status IN ('pending_review', 'ai_suggested', 'flagged')"""),
                {"eid": entity.id}
            )
            count = count_res.scalar() or 0
            if count > 0:
                await dispatch.send(
                    entity_id=entity.id,
                    notification_type='uncategorized',
                    channel='sms',
                    context={"count": count,
                             "dashboard_url": dispatch.get_dashboard_url("/review")},
                    session=session,
                )
```

**2. Suppress per-transaction `uncategorized` SMS in [sync.py](src/zalazar/plaid/sync.py)**

Change `channel='both'` to `channel='email'` (or remove it entirely) on line 202 so
the immediate per-transaction alert does not also SMS — the digest handles that.

---

## GAP C — Cash Flow Change: no scheduler job

### What should happen
Every day at **7:45 AM**, if month-to-date spend has shifted by more than
`cash_flow_change_pct` (default 20%) versus the same period last month, an SMS fires:
> *"Cash Flow Alert: A significant change of -35.0% was detected for May 2026."*

### What actually happens
The `cash_flow_change.jinja2` template exists and renders correctly.
`notification_settings.cash_flow_change_pct` stores the threshold.
**No code ever calculates the delta or calls `dispatch.send`.**

### What needs to be added
**New scheduler job in [scheduler.py](src/zalazar/scheduler.py)** registered at 07:45:

```python
self.scheduler.add_job(
    self.run_cash_flow_check,
    CronTrigger(hour=7, minute=45),
    name="cash_flow_check"
)
```

Job logic:
1. For each entity, query MTD spend (current month) and same-period-last-month spend.
2. Calculate `delta_pct = (mtd_current - mtd_prior) / abs(mtd_prior) * 100`.
3. Read `cash_flow_change_pct` threshold from `notification_settings` for that entity.
4. If `abs(delta_pct) >= threshold`, call `dispatch.send` with `notification_type='cash_flow_change'`.

---

## GAP D — Plaid Auth Alert uses the wrong notification type

### What should happen
When `ITEM_LOGIN_REQUIRED` or `PENDING_EXPIRATION` fires, the user should receive
a notification categorised as a **Plaid auth alert** — distinct from a balance
reconciliation problem — with a direct re-authentication link.

### What actually happens
In [webhooks.py](src/zalazar/plaid/webhooks.py) lines 123–136, `ITEM_LOGIN_REQUIRED`
calls `dispatch.send` with `notification_type='reconciliation_mismatch'`. The SMS
and email arrive, but:
- The `notification_log` row is recorded as `reconciliation_mismatch`, making reports
  misleading (auth events inflate the reconciliation failure count).
- The message body says "reconciliation mismatch" rather than "re-authentication required".

### What needs to be fixed
This is a two-step fix:

**1. Add `plaid_auth_alert` to the DB enum** (new migration):
```sql
ALTER TYPE notification_type ADD VALUE 'plaid_auth_alert';
```

**2. Create templates** `src/zalazar/notifier/templates/plaid_auth_alert.jinja2`:
```
Action required: {{ account }} needs re-authentication.
Re-link your account: {{ reauth_url }}
```

**3. Update [webhooks.py](src/zalazar/plaid/webhooks.py)** to use the new type:
```python
await dispatch.send(
    entity_id=entity_id,
    notification_type='plaid_auth_alert',   # ← was 'reconciliation_mismatch'
    channel='both',
    context={
        "account": f"{account.bank_name} – {account.account_name}",
        "reauth_url": dispatch.get_dashboard_url(f"/reconnect?item_id={item_id}"),
    },
    session=session,
)
```

---

## GAP E — PENDING_EXPIRATION webhook fires no notification

### What should happen
When Plaid sends `PENDING_EXPIRATION` (token expiring in 7 days), an SMS + Email
should alert the user to re-link the account **before** it stops syncing — giving
them time to act without a service disruption.

### What actually happens
[webhooks.py](src/zalazar/plaid/webhooks.py) lines 160–161:
```python
elif webhook_code == "PENDING_EXPIRATION":
    logger.warning("PENDING_EXPIRATION", item_id=item_id)
```
The handler logs the warning and **does nothing else**. No notification is sent.
The user only finds out when the account eventually shows `ITEM_LOGIN_REQUIRED`
(by which point syncing has already stopped).

### What needs to be added
In [webhooks.py](src/zalazar/plaid/webhooks.py) after the `logger.warning` on line 161:

```python
elif webhook_code == "PENDING_EXPIRATION":
    logger.warning("PENDING_EXPIRATION", item_id=item_id)
    await dispatch.send(
        entity_id=entity_id,
        notification_type='plaid_auth_alert',   # requires GAP D to be closed first
        channel='both',
        context={
            "account": f"{account.bank_name} – {account.account_name}",
            "reauth_url": dispatch.get_dashboard_url(f"/reconnect?item_id={item_id}"),
        },
        session=session,
    )
```

> **Dependency:** Closing GAP E requires GAP D to be done first (the `plaid_auth_alert`
> type and template must exist before this dispatch call will render correctly).

---

## GAP F — Nightly Sync Status: no trigger and no template

### What should happen
After the nightly sync job completes (success **or** failure), an email should arrive
summarising what happened:
> **Success:** *"Nightly sync complete. 3 accounts synced, 47 new transactions added."*
> **Failure:** *"Nightly sync FAILED. Error: Connection timeout after 30s."*

### What actually happens
[services/worker/jobs.py](services/worker/jobs.py) `plaid_daily_sync()` (lines 11–49):
- Updates `job_runs` to `success` or `failed`.
- Logs the result with `structlog`.
- **Never calls `dispatch.send`** in either the success path (line 40) or the except
  block (line 43).

There is also **no `nightly_sync_status` Jinja2 template** in
`src/zalazar/notifier/templates/`.

### What needs to be added

**1. Create templates**

`src/zalazar/notifier/templates/nightly_sync_status.jinja2`:
```
Nightly Sync {{ "SUCCESS" if success else "FAILED" }}: {{ accounts_synced }} accounts, {{ transactions_added }} new transactions.{% if error %} Error: {{ error }}{% endif %}
```

`src/zalazar/notifier/templates/nightly_sync_status.html.jinja2` — an HTML version
extending `base_email.html.jinja2`.

**2. Add `nightly_sync_status` to the DB enum** (new migration):
```sql
ALTER TYPE notification_type ADD VALUE 'nightly_sync_status';
```

**3. Hook into [services/worker/jobs.py](services/worker/jobs.py)**

After `await session.commit()` on line 40 (success path):
```python
await dispatch.send(
    entity_id=None,          # admin-level notification, not per-entity
    notification_type='nightly_sync_status',
    channel='email',
    context={
        "success": True,
        "accounts_synced": len(accounts),
        "transactions_added": total_tx_count,   # accumulate in the loop
        "error": None,
    },
)
```

After `await session.commit()` in the except block (line 48):
```python
await dispatch.send(
    entity_id=None,
    notification_type='nightly_sync_status',
    channel='email',
    context={
        "success": False,
        "accounts_synced": 0,
        "transactions_added": 0,
        "error": str(e),
    },
)
```

> **Note:** `entity_id=None` requires a small change to `dispatch._send_impl` — it
> currently expects a UUID. The nightly sync status is an admin notification, not
> per-entity, so the dispatcher needs to fall back to `settings.EMAIL_RECIPIENT`
> unconditionally when `entity_id` is `None`.

---

## Dependency Order for Closing All Gaps

```
GAP D (add plaid_auth_alert type + template)
    └── GAP E (wire PENDING_EXPIRATION webhook)   ← depends on D

GAP A (income_received trigger in sync.py)        ← independent
GAP B (review digest scheduler job)               ← independent
GAP C (cash flow change scheduler job)            ← independent
GAP F (nightly sync status)                       ← independent, needs new type + template
```

Recommended order: **A → B → C → D → E → F**
