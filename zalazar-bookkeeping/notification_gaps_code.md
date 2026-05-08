# Notification Gaps — Code Walkthrough

How each gap plays out step-by-step through the actual production code.

---

## GAP A — Income Received

**Real-world event:** Tenant pays $2,000 rent. Plaid picks it up and the nightly sync runs.

### Execution path today

```
scheduler.py:52       run_nightly_sync()
                        └─ sync_account(acc.id)

plaid/sync.py:19      sync_account(account_id)
                        └─ calls Plaid API → gets added transactions
                        └─ for each tx: process_transaction(session, account, tx)

plaid/sync.py:114     process_transaction(session, account, plaid_tx)
  :116                  amount = -Decimal(plaid_tx['amount'])
                        # Plaid stores outflows as positive, so this inverts the sign.
                        # A $2,000 rent DEPOSIT from Plaid looks like amount = -2000.00
                        # After sign inversion:  amount = +2000.00  ← positive = income

  :150                  classification = await classify_transaction(...)
                        # classifier assigns  type='income', status='auto_categorized'

  :193                  INSERT INTO transactions ...  ← row written to DB

  :197                  if classification['status'] == 'pending_review':   ← FALSE (it's auto_categorized)
                            dispatch.send(uncategorized ...)  ← SKIPPED

  :236                  if amount < -1000:                                  ← FALSE (+2000 is not < -1000)
                            dispatch.send(large_expense ...)  ← SKIPPED

                        # function ends — no notification sent
```

**The gap:** The two `if` blocks at lines 197 and 236 are the only notification
triggers. `amount = +2000` passes neither check. The transaction is saved to the DB
and processing ends silently.

### What the fix looks like

Add a third block immediately after line 251:

```python
# plaid/sync.py — after the large_expense block (line 251)
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

## GAP B — Review Required Daily Digest

**Real-world event:** The AI couldn't classify 12 transactions overnight.
The plan wants one 9 AM SMS: *"12 transactions waiting for review."*

### Execution path today

```
plaid/sync.py:197     if classification['status'] == 'pending_review':
                          asyncio.create_task(
                              dispatch.send(
                                  notification_type='uncategorized',
                                  channel='both',        ← SMS + Email per transaction
                                  context={
                                      "vendor": "...",
                                      "amount": "...",   ← single-transaction context, no count
                                  }
                              )
                          )
```

This fires **12 times** — once per transaction, all within seconds of each other,
all at 4 AM when sync runs.

The scheduler in `scheduler.py` runs these three jobs:

```
scheduler.py:21    run_nightly_sync       CronTrigger(hour=4,  minute=0)
scheduler.py:28    run_daily_reconciliation CronTrigger(hour=4, minute=30)
scheduler.py:35    run_weekly_summary     CronTrigger(day_of_week='mon', hour=5)
```

**There is no job at 9 AM.** The `run_weekly_summary` method exists but fires only
on Mondays and sends a P&L summary, not a review queue count.

### What the fix looks like

**1. Register the job in `scheduler.py __init__`:**
```python
self.scheduler.add_job(
    self.run_review_digest,
    CronTrigger(hour=9, minute=0),
    name="review_digest"
)
```

**2. Add the method to the Scheduler class:**
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

**3. Suppress the per-transaction SMS in `sync.py` line 202** — change `channel='both'`
to `channel='email'` so AI-uncertain transactions still log to email but no longer
carpet-bomb SMS at 4 AM.

---

## GAP C — Cash Flow Change

**Real-world event:** May expenses are running 35% below April at the same point in
the month — a meaningful signal. Nobody is told.

### Execution path today

```
scheduler.py       run_nightly_sync   04:00  ← syncs transactions only
scheduler.py       run_daily_reconciliation  ← checks balances only
                   (no cash-flow delta calculation anywhere)
```

`cash_flow_change.jinja2` exists. `notification_settings.cash_flow_change_pct`
stores the threshold (default 20%). But **no function ever reads that threshold,
calculates a delta, or calls `dispatch.send`**. The template and setting sit unused.

### What the fix looks like

Add a new scheduler job and method:

```python
# scheduler.py — register at 07:45
self.scheduler.add_job(
    self.run_cash_flow_check,
    CronTrigger(hour=7, minute=45),
    name="cash_flow_check"
)

async def run_cash_flow_check(self):
    today = date.today()
    day_of_month = today.day
    this_month_start = today.replace(day=1)
    # Same period last month: day 1 to today's day-of-month
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    last_month_same_day = last_month_start.replace(day=min(day_of_month, last_month_end.day))

    async with AsyncSessionLocal() as session:
        entities = (await session.execute(text("SELECT id FROM entities"))).fetchall()
        for entity in entities:
            settings_row = (await session.execute(
                text("SELECT cash_flow_change_pct FROM notification_settings WHERE entity_id = :eid"),
                {"eid": entity.id}
            )).fetchone()
            threshold = float(settings_row.cash_flow_change_pct) if settings_row else 20.0

            mtd = (await session.execute(text("""
                SELECT COALESCE(SUM(amount),0) FROM transactions
                WHERE entity_id=:eid AND amount<0
                AND transaction_date BETWEEN :start AND :end"""),
                {"eid": entity.id, "start": this_month_start, "end": today}
            )).scalar()

            prior = (await session.execute(text("""
                SELECT COALESCE(SUM(amount),0) FROM transactions
                WHERE entity_id=:eid AND amount<0
                AND transaction_date BETWEEN :start AND :end"""),
                {"eid": entity.id, "start": last_month_start, "end": last_month_same_day}
            )).scalar()

            if prior and prior != 0:
                delta_pct = (float(mtd) - float(prior)) / abs(float(prior)) * 100
                if abs(delta_pct) >= threshold:
                    await dispatch.send(
                        entity_id=entity.id,
                        notification_type='cash_flow_change',
                        channel='sms',
                        context={
                            "delta": f"{delta_pct:+.1f}%",
                            "period": today.strftime("%B %Y"),
                            "dashboard_url": dispatch.get_dashboard_url("/cashflow"),
                        },
                        session=session,
                    )
```

---

## GAP D — Auth Alert Uses Wrong Notification Type

**Real-world event:** Chase requires re-login. `ITEM_LOGIN_REQUIRED` webhook fires.

### Execution path today

```
plaid/webhooks.py:112   elif webhook_code == "ITEM_LOGIN_REQUIRED":
  :113-118                UPDATE bank_accounts SET is_active=FALSE ...  ← correct
  :120-136                await dispatch.send(
                              entity_id=entity_id,
                              notification_type='reconciliation_mismatch',  ← WRONG TYPE
                              channel='both',
                              context={
                                  "diff": "0.00",
                                  "account": "Chase – Checking",
                                  "plaid_balance": "N/A – re-authentication required",
                                  "calculated_balance": "N/A",
                              }
                          )
```

The notification **does arrive** — but the DB row in `notification_log` is recorded as:
```
notification_type = 'reconciliation_mismatch'
```

This means:
- Any query counting reconciliation mismatches is inflated by auth events.
- The email subject line reads *"Alert: Reconciliation Mismatch"* instead of
  *"Action Required: Re-authenticate Chase"*.
- The SMS body comes from `reconciliation_mismatch.jinja2` which renders
  *"Reconciliation mismatch of $0.00 on account Chase – Checking"* — confusing
  and inaccurate.

### What the fix looks like

1. New migration (`v3_4_notification_types.sql`):
```sql
ALTER TYPE notification_type ADD VALUE 'plaid_auth_alert';
```

2. New template `src/zalazar/notifier/templates/plaid_auth_alert.jinja2`:
```
Action required: {{ account }} needs re-authentication.
Re-link now: {{ reauth_url }}
```

3. Update `dispatch.py` `_is_enabled` mapping and `_subject_for`:
```python
'plaid_auth_alert': user_settings.get('notify_plaid_auth', True),
```
```python
'plaid_auth_alert': "Action Required: Re-authenticate Bank Account",
```

4. Update `webhooks.py` lines 123-136 and 145-158 to use the new type.

---

## GAP E — PENDING_EXPIRATION Does Nothing

**Real-world event:** Plaid sends a warning 7 days before a token expires.
This is the advance-notice window to re-link before syncing breaks.

### Execution path today

```
plaid/webhooks.py:80    async def handle_webhook(session, payload):
  :82                     webhook_type = payload.get("webhook_type")   # "TRANSACTIONS"
  :83                     webhook_code = payload.get("webhook_code")   # "PENDING_EXPIRATION"
  :86                     if webhook_type != "TRANSACTIONS": return     # passes through
  :98                     account = session.execute(SELECT ... WHERE plaid_item_id=...).fetchone()

  :110                    if webhook_code in ("DEFAULT_UPDATE", ...):
                              asyncio.create_task(sync_account(...))   # not this branch

  :112                    elif webhook_code == "ITEM_LOGIN_REQUIRED":  # not this branch

  :138                    elif webhook_code == "USER_PERMISSION_REVOKED": # not this branch

  :160                    elif webhook_code == "PENDING_EXPIRATION":
  :161                        logger.warning("PENDING_EXPIRATION", item_id=item_id)
                              # ← function ends here. Nothing else happens.
```

Plaid fires this webhook once. If it's ignored, the next signal is `ITEM_LOGIN_REQUIRED`
7 days later — by which point syncing has already stopped and the user has missed
a week of transactions.

### What the fix looks like

```python
# plaid/webhooks.py line 160 — replace the two-line stub
elif webhook_code == "PENDING_EXPIRATION":
    logger.warning("PENDING_EXPIRATION", item_id=item_id)
    await dispatch.send(
        entity_id=entity_id,
        notification_type='plaid_auth_alert',   # requires GAP D closed first
        channel='both',
        context={
            "account": f"{account.bank_name} – {account.account_name}",
            "reauth_url": dispatch.get_dashboard_url(
                f"/reconnect?item_id={item_id}"
            ),
        },
        session=session,
    )
```

---

## GAP F — Nightly Sync Status Never Sent

**Real-world event:** The 4 AM sync runs. It either succeeds (47 new transactions)
or crashes (Plaid API timeout). Either way, no email is sent.

### Execution path today — Success

```
services/worker/jobs.py:11   async def plaid_daily_sync():
  :14                          INSERT INTO job_runs ... status='running'
  :26-29                       SELECT id FROM bank_accounts WHERE is_active=TRUE
  :31-33                       for account in accounts:
                                   await sync_account(account.id)
  :36-40                       UPDATE job_runs SET status='success', ended_at=NOW()
                               await session.commit()
                               # ← function returns. No dispatch.send call.
```

### Execution path today — Failure

```
services/worker/jobs.py:42   except Exception as e:
  :43                          logger.error("Daily sync failed", error=str(e))
  :44-48                       UPDATE job_runs SET status='failed', error_message=:error
                               await session.commit()
                               raise
                               # ← exception re-raised. No dispatch.send call.
```

The `job_runs` table gets updated correctly — but it's a DB row. Nobody reads it
unless they log into Supabase directly. At 4 AM when a sync fails silently, the
user wakes up, opens the dashboard, and sees stale data with no explanation.

### What the fix looks like

**1. Create template `src/zalazar/notifier/templates/nightly_sync_status.jinja2`:**
```
Nightly Sync {{ "SUCCESS" if success else "FAILED" }}: {{ accounts_synced }} account(s), {{ transactions_added }} new transaction(s).{% if error %} Error: {{ error }}{% endif %}

Dashboard: {{ dashboard_url }}
```

**2. New migration — add the type:**
```sql
ALTER TYPE notification_type ADD VALUE 'nightly_sync_status';
```

**3. Hook into `services/worker/jobs.py`:**

```python
async def plaid_daily_sync():
    async with AsyncSessionLocal() as session:
        result = await session.execute(...)
        run_id = result.scalar_one()
        await session.commit()

        total_added = 0   # ← track count across all accounts

        try:
            accounts_result = await session.execute(...)
            accounts = accounts_result.fetchall()

            for account in accounts:
                count_before = await _tx_count(session, account.id)
                await sync_account(account.id)
                count_after = await _tx_count(session, account.id)
                total_added += (count_after - count_before)

            await session.execute(
                text("UPDATE job_runs SET status='success', ended_at=NOW() WHERE id=:id"),
                {"id": run_id}
            )
            await session.commit()

            # ← ADD THIS
            await dispatch.send(
                entity_id=None,
                notification_type='nightly_sync_status',
                channel='email',
                context={
                    "success": True,
                    "accounts_synced": len(accounts),
                    "transactions_added": total_added,
                    "error": None,
                    "dashboard_url": settings.DASHBOARD_URL,
                },
            )

        except Exception as e:
            logger.error("Daily sync failed", error=str(e))
            await session.execute(
                text("UPDATE job_runs SET status='failed', error_message=:err, ended_at=NOW() WHERE id=:id"),
                {"err": str(e), "id": run_id}
            )
            await session.commit()

            # ← ADD THIS
            await dispatch.send(
                entity_id=None,
                notification_type='nightly_sync_status',
                channel='email',
                context={
                    "success": False,
                    "accounts_synced": 0,
                    "transactions_added": 0,
                    "error": str(e),
                    "dashboard_url": settings.DASHBOARD_URL,
                },
            )
            raise
```

> **Note on `entity_id=None`:** `dispatch._send_impl` currently requires a UUID
> for `entity_id`. A small guard is needed so that when `entity_id` is `None`,
> the dispatcher skips the `notification_settings` lookup and falls back directly
> to `settings.EMAIL_RECIPIENT`. This makes nightly sync an admin-level
> notification rather than a per-entity one.

---

## Dependency Map

```
GAP D ──► must be done before ──► GAP E
  (add plaid_auth_alert type)        (wire PENDING_EXPIRATION)

GAP A   independent   (1 line in sync.py)
GAP B   independent   (new scheduler method + suppress SMS in sync.py)
GAP C   independent   (new scheduler method)
GAP F   independent   (new template + hooks in jobs.py + entity_id=None guard)
```

Recommended implementation order: **A → D → E → B → C → F**
