# AI Bookkeeping System — Production Implementation Plan (v2)
**Client:** Zalazar Holdings LLC
**Scope:** Section 11 — Bookkeeping module
**Stack:** Python 3.11+ only (no n8n)
**Database:** Supabase (Postgres) — schema v3.1 already applied
**Version:** 2.0 · Supersedes v1

---

## What changed from v1

| Area | v1 assumption | v2 (this plan) |
|---|---|---|
| Orchestration | n8n cron + webhooks | Python APScheduler worker + FastAPI |
| Schema | Proposed from scratch | Implementing against **existing** v3.1 schema |
| Property assignment | Single `property_id` on transactions | Multi-property `transaction_allocations` (direct / even_split / custom) |
| Categorization | AI could auto-categorize at ≥0.80 | **AI never auto-categorizes.** Only rule matches ≥0.95 hit `auto_categorized`. AI output → `ai_suggested` for human approval |
| Summary storage | `daily_summaries` table | `monthly_property_pnl` materialized view, refreshed nightly |
| Review threshold | Binary (auto vs review) | Four states: `auto_categorized`, `ai_suggested`, `flagged`, `excluded` |
| Mortgage handling | Not addressed | Split into interest + principal transactions, escrow tracked separately |
| Transfer handling | Flag only | `paired_transaction_id` linking both legs, status `excluded` |

---

## 0. Guiding principles (unchanged)

1. **No silent failure.** Every pipeline that touches money logs success/failure, alerts on exception, and is idempotent.
2. **The schema is the contract.** All invariants are enforced at the database level (allocation sum, leaf-only accounts, account_type ↔ is_pnl). The Python code is a client of those rules, not a re-implementation.
3. **Every AI decision is reversible.** AI never writes to `auto_categorized`. Human approval is required before a transaction affects P&L.

### Domain note: why the AI-never-auto-categorizes rule matters
In v1 I proposed AI could auto-approve at confidence ≥ 0.80. Your schema explicitly forbids that — `ai_suggested` transactions carry no allocations and don't appear in P&L until a human approves. This is the right call for a financial product but it reshapes the QA target: **"80% automatic" becomes achievable only once `vendor_rules` has been seeded/grown to cover the high-frequency vendors.** Ramping that rule set is a dedicated workstream (Milestone 4), not a side effect of AI classification.

---

## Stack decisions

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Single stack across API, workers, scripts. |
| Web framework | **FastAPI** | Async, webhook-friendly, OpenAPI auto-generated. |
| Scheduler | **APScheduler 3.x** with `SQLAlchemyJobStore` pointed at Supabase | Persistent across restarts, jobs survive deploys, run history queryable. |
| DB client | **supabase-py** for simple ops, **SQLAlchemy 2.x + asyncpg** for complex queries/materialized view refresh | Two clients is fine — Supabase client for row CRUD, SQLAlchemy for batch and DDL. |
| Task execution | **No Celery.** Long jobs run in APScheduler worker directly. | Celery is overkill for one-client scale. Revisit if job volume grows. |
| Validation | **Pydantic v2** | Matches FastAPI, serializes to/from schema cleanly. |
| Plaid | `plaid-python` | — |
| AI | `openai` (SDK v1+) with structured outputs | — |
| SMS | `twilio` | — |
| Email | `google-api-python-client` + `google-auth-oauthlib` (Gmail API) | — |
| Logging | `structlog` + Sentry | JSON logs to stdout, Sentry for errors. |
| Testing | `pytest`, `pytest-asyncio`, `httpx` (for API), `responses`/`vcr.py` for Plaid/OpenAI | — |
| Deployment | Docker, two services (`api`, `worker`), `docker-compose.yml` in dev, client VPS in prod | — |
| CI/CD | GitHub Actions | Lint → test → build → deploy on tag. |

### Process topology
```
┌─────────────────────┐          ┌─────────────────────┐
│   api (FastAPI)     │          │   worker            │
│                     │          │   (APScheduler)     │
│ - /plaid/link       │          │                     │
│ - /plaid/webhook    │          │ - plaid_daily_sync  │
│ - /queue/*          │          │ - reconcile_daily   │
│ - /jarvis/ask       │          │ - refresh_monthly   │
│ - /twilio/webhook   │          │ - weekly_summary    │
│ - /health           │          │ - notifications_rtx │
└──────────┬──────────┘          └──────────┬──────────┘
           │                                 │
           └────────────┬────────────────────┘
                        ▼
         ┌───────────────────────────┐
         │  shared package (src/)    │
         │  normalizer, classifier,  │
         │  allocator, reconciler,   │
         │  notifier, jarvis, plaid  │
         └─────────────┬─────────────┘
                       ▼
              ┌─────────────────┐
              │  Supabase       │
              │  (Postgres)     │
              └─────────────────┘
```

Both services import from the same `src/` package. The scheduler and the API can be deployed independently; if the API restarts, scheduled jobs keep running.

---

## Repository structure

```
zalazar-bookkeeping/
├── src/
│   ├── zalazar/
│   │   ├── __init__.py
│   │   ├── config.py              # Settings (Pydantic BaseSettings)
│   │   ├── db.py                  # SQLAlchemy session, Supabase client
│   │   ├── models.py              # Pydantic models matching schema
│   │   ├── plaid/
│   │   │   ├── client.py          # Plaid client wrapper
│   │   │   ├── sync.py            # /transactions/sync cursor logic
│   │   │   ├── link.py            # Link token flow
│   │   │   └── webhooks.py        # Webhook handlers + signature verification
│   │   ├── normalizer.py          # Clean merchant/description (pure functions)
│   │   ├── classifier.py          # Rule match → AI fallback
│   │   ├── allocator.py           # Property allocation (3-layer engine)
│   │   ├── reconciler.py          # Daily reconciliation
│   │   ├── reports.py             # Materialized view refresh + on-demand P&L
│   │   ├── notifier/
│   │   │   ├── dispatch.py        # Unified dispatch with notification_log
│   │   │   ├── sms.py             # Twilio
│   │   │   ├── email.py           # Gmail API
│   │   │   └── templates/         # Jinja2 templates per notification_type
│   │   ├── jarvis/
│   │   │   ├── agent.py           # Agent loop with tool calls
│   │   │   └── tools.py           # query_summary, query_transactions, etc.
│   │   ├── mortgage.py            # Interest/principal splitter
│   │   ├── transfers.py           # Transfer pair detection
│   │   └── audit.py               # audit_log helper
│   └── __init__.py
├── services/
│   ├── api/
│   │   ├── main.py                # FastAPI app factory
│   │   ├── routes/
│   │   │   ├── plaid.py
│   │   │   ├── queue.py
│   │   │   ├── jarvis.py
│   │   │   ├── reports.py
│   │   │   └── health.py
│   │   └── Dockerfile
│   └── worker/
│       ├── main.py                # APScheduler BlockingScheduler
│       ├── jobs.py                # Job definitions
│       └── Dockerfile
├── migrations/
│   ├── v3_0_initial.sql           # Your current schema
│   ├── v3_1_notifications.sql     # Your current migration
│   └── v3_2_job_runs.sql          # New — see §1
├── tests/
│   ├── fixtures/
│   │   ├── plaid_responses/
│   │   ├── qa_transactions.json   # 50+ hand-labeled transactions
│   │   └── sample_statements/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── scripts/
│   ├── backfill_plaid.py
│   ├── seed_vendor_rules.py       # Bulk import vendor rules from historical
│   ├── seed_chart_of_accounts.py  # Leaf + parent accounts, is_assignable
│   ├── run_qa.py                  # QA harness (accuracy reporting)
│   └── split_mortgage.py          # CLI helper for manual mortgage splits
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── RUNBOOK.md
└── README.md
```

---

## Milestone 0 — Project setup + Plaid production application

**Duration:** 1 week · **Critical path blocker:** Plaid review runs in parallel, 2–4 weeks

### 0.1 Plaid production application — submit day 1
Application must list:
- Registered business: **Zalazar Holdings LLC** (client is the account holder)
- Products: `transactions`, `auth`, `identity`, `accounts`
- Data use: internal bookkeeping automation (not resold or shared)
- Webhook URL (placeholder OK at submission, finalized before go-live)

While approval is pending, build against Plaid **sandbox** → then **development tier** (real credentials, limited institutions) once sandbox work stabilizes.

### 0.2 Environments
- `local` — sandbox Plaid, OpenAI dev key with low spend cap, Twilio test creds, Supabase local dev or a shared dev project.
- `staging` — Plaid development tier, real OpenAI key, Twilio sandbox number, dedicated Supabase project.
- `production` — Plaid production, real OpenAI, real Twilio number, client-owned Gmail, production Supabase.

### 0.3 Dependencies (pin exact versions)
```toml
[project]
dependencies = [
    "fastapi==0.115.*",
    "uvicorn[standard]==0.32.*",
    "pydantic==2.10.*",
    "pydantic-settings==2.6.*",
    "sqlalchemy[asyncio]==2.0.*",
    "asyncpg==0.30.*",
    "supabase==2.10.*",
    "apscheduler==3.10.*",
    "plaid-python==27.*",
    "openai==1.54.*",
    "twilio==9.3.*",
    "google-api-python-client==2.150.*",
    "google-auth-oauthlib==1.2.*",
    "structlog==24.4.*",
    "sentry-sdk[fastapi]==2.18.*",
    "httpx==0.27.*",
    "jinja2==3.1.*",
    "cryptography==43.*",
]

[project.optional-dependencies]
dev = ["pytest==8.3.*", "pytest-asyncio==0.24.*", "responses==0.25.*", "vcrpy==6.*", "ruff==0.7.*", "mypy==1.13.*"]
```

### 0.4 Secrets
- Local: `.env` via `pydantic-settings`, not committed.
- Staging/prod: **Doppler** (recommended) or AWS Secrets Manager. Never hard-code the Plaid access token encryption key.
- Plaid access tokens: encrypted **at the application layer** before hitting Postgres. Your schema already has `plaid_access_token_encrypted` — use Fernet (`cryptography` library) with the key in secrets.

### 0.5 Acceptance
- [ ] Plaid production application submitted, confirmation saved.
- [ ] Repo structure as above, `docker-compose up` launches api + worker + optional local Postgres.
- [ ] GitHub Actions: lint + type-check + tests on every push.
- [ ] `.env.example` documents every required variable.
- [ ] `cryptography.Fernet` wrapper for Plaid tokens unit-tested.

---

## Milestone 1 — Schema verification + additions

**Duration:** 1–2 days · **Dependencies:** M0

Your schema v3.1 is already applied. This milestone verifies it and adds two pieces the current schema doesn't cover.

### 1.1 Verification checklist
- [ ] All enums present (`entity_type`, `account_type`, `transaction_status`, `source_type`, `allocation_method`, `reconciliation_status`, `movement_type`, `notification_type`, `notification_channel`, `notification_delivery_status`).
- [ ] All 14 tables present.
- [ ] Triggers verified:
  - `check_transaction_account_assignable` — leaf-only account assignment
  - `check_allocations_match_transaction` — allocation sum invariant
  - `check_transaction_has_allocations` — status transition invariant
  - `invalidate_reports_for_transaction` / `_for_allocation` — cache invalidation
  - `set_updated_at` on all 6 updatable tables
- [ ] Materialized view `monthly_property_pnl` exists with unique index.
- [ ] RLS enabled on all 13 tables (14 with `notification_log`).
- [ ] Trigram index `idx_vendor_rules_pattern_trgm` exists.

### 1.2 New migration — `v3_2_job_runs.sql`
The schema has `audit_log` (good for data-change audit) and `notification_log` (good for SMS/email delivery) but **nothing tracks scheduled job execution**. Without this, a missed daily sync is invisible. Add:

```sql
BEGIN;

CREATE TYPE job_status AS ENUM ('running', 'success', 'partial', 'failed');

CREATE TABLE job_runs (
  id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
  job_name          TEXT        NOT NULL,
  started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at          TIMESTAMPTZ,
  status            job_status  NOT NULL DEFAULT 'running',
  records_processed INT         DEFAULT 0,
  records_failed    INT         DEFAULT 0,
  error_message     TEXT,
  metadata          JSONB,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_job_runs_job_started ON job_runs(job_name, started_at DESC);
CREATE INDEX idx_job_runs_status      ON job_runs(status) WHERE status IN ('running','failed');

ALTER TABLE job_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON job_runs FOR ALL TO authenticated USING (TRUE) WITH CHECK (TRUE);

COMMIT;
```

Every scheduled job opens a `job_runs` row on start, updates it on finish. Zero exceptions.

### 1.3 Seed: chart of accounts
Run `scripts/seed_chart_of_accounts.py` idempotently. Structure matches §11.4 with leaf/parent hierarchy:

```
Income (parent, is_assignable=FALSE)
  Rental Income (leaf, account_type=income, is_pnl=TRUE)
  Other Income (leaf, account_type=income, is_pnl=TRUE)

Operating Expenses (parent, is_assignable=FALSE)
  Repairs & Maintenance (leaf, account_type=operating_expense)
  Utilities (leaf, operating_expense)
  Property Management Fees (leaf, operating_expense)
  HOA Fees (leaf, operating_expense)
  Insurance (leaf, operating_expense)
  Property Taxes (leaf, operating_expense)
  Legal & Professional (leaf, operating_expense)
  Advertising (leaf, operating_expense)
  Travel & Transportation (leaf, operating_expense)
  Bank Fees (leaf, operating_expense)
  Other Expense (leaf, operating_expense)

Property Costs (parent, is_assignable=FALSE)
  Mortgage Interest (leaf, account_type=property_cost, is_pnl=TRUE)
  Capital Improvements (leaf, property_cost, is_pnl=TRUE)

Capital Accounts (parent, is_assignable=FALSE)
  Principal Reduction (leaf, account_type=capital_non_expense, is_pnl=FALSE)
  Owner Distributions (leaf, capital_non_expense, is_pnl=FALSE)
  Owner Contributions (leaf, capital_non_expense, is_pnl=FALSE)

Transfers (parent, is_assignable=FALSE)
  Internal Transfer (leaf, account_type=transfer, is_pnl=FALSE)
```

Each leaf has a stable `code` (e.g., `INC-RENT`, `EXP-REPAIRS`, `CAP-PRIN`) that Python code references instead of UUIDs.

### 1.4 Seed: entities and properties
Run `scripts/seed_entities_properties.py` with client's actual entity and property list. Include split address (street, city, state, zip) so Layer 1 allocator works.

### 1.5 Acceptance
- [ ] All schema verification checks pass.
- [ ] `v3_2_job_runs.sql` applied, `job_runs` table usable.
- [ ] Chart of accounts seeded (parents + leaves, correct is_pnl and is_assignable flags).
- [ ] Entities and properties seeded from client data.
- [ ] Test: attempting to assign a transaction to a parent account raises the trigger error.
- [ ] Test: attempting to mark a transaction `reviewed` without allocations raises the trigger error.

---

## Milestone 2 — Plaid integration

**Duration:** 1.5 weeks · **Dependencies:** M0, M1

### 2.1 Plaid Link flow (one-time account connection)
FastAPI endpoints:
```
POST /plaid/link-token       → returns link_token for frontend
POST /plaid/exchange-token   → body: {public_token, metadata} → persists account
```

The "frontend" can be a minimal HTML page served by FastAPI (Jinja2 template) — no React needed for a single-user workflow. It loads Plaid Link JS, calls `/plaid/link-token` on mount, and posts the `public_token` back to `/plaid/exchange-token` on success.

On `exchange-token`:
1. Exchange `public_token` → `access_token` + `item_id`.
2. Encrypt access token with Fernet.
3. Fetch account metadata (`/accounts/get`).
4. For each account in the Item, upsert a row in `bank_accounts` with `plaid_account_id`, `plaid_item_id`, encrypted token, institution name, account name, `account_last4`, `account_type` mapped to your CHECK values.
5. Fire `INITIAL_UPDATE` webhook will arrive later; historical backfill runs on that or on manual trigger.

**Security invariant:** the client authenticates with their bank through Plaid's own UI. Bank credentials never touch our code.

### 2.2 Historical backfill
`scripts/backfill_plaid.py`:
- For each `bank_accounts` row with `plaid_access_token_encrypted IS NOT NULL` and `plaid_cursor IS NULL`:
  - Call `/transactions/sync` with empty cursor.
  - Paginate through `has_more`.
  - Run every returned transaction through the full pipeline (normalize → classify → allocate).
  - Persist `next_cursor` to `bank_accounts.plaid_cursor`.
- Write a single `job_runs` row with total counts and errors.

**Run this backfill even on historical data** — the rule learning from corrections is retroactive. A vendor rule created from a correction today auto-applies to any future transaction, but also surfaces historical misses for batch reclassification.

### 2.3 Daily sync job
APScheduler cron on the `worker` service, `hour=6, minute=0` local time:

```python
@scheduler.scheduled_job('cron', hour=6, minute=0, id='plaid_daily_sync', coalesce=True, max_instances=1)
async def plaid_daily_sync():
    run = await job_runs.start('plaid_daily_sync')
    try:
        for account in await db.get_active_accounts():
            await sync_account(account)  # uses stored cursor
        await job_runs.finish(run, 'success')
    except Exception as e:
        await job_runs.finish(run, 'failed', error=str(e))
        capture_exception(e)
        raise
```

`coalesce=True` + `max_instances=1` ensures a missed run doesn't stack and a slow run doesn't double up.

### 2.4 Webhook listener
`POST /plaid/webhook` handles these codes from Plaid:
| Code | Action |
|---|---|
| `INITIAL_UPDATE`, `HISTORICAL_UPDATE`, `DEFAULT_UPDATE` | Trigger sync for that item |
| `SYNC_UPDATES_AVAILABLE` | Trigger sync (incremental) |
| `ITEM_LOGIN_REQUIRED` | Set `bank_accounts.plaid_last_error`, status-alert the client via SMS + email |
| `PENDING_EXPIRATION` | Email client 7 days before expiry |
| `USER_PERMISSION_REVOKED` | Deactivate account (`is_active=FALSE`), alert client |

Signature verification is **required**: Plaid sends a `Plaid-Verification` JWT header; verify against Plaid's JWKS endpoint. Any request failing verification returns 401 and is logged.

### 2.5 Error handling matrix
| Condition | Response |
|---|---|
| Plaid 5xx | Exponential backoff (2, 4, 8, 16, 32 sec), max 5 retries. Then fail job, SMS. |
| Plaid 429 | Respect `Retry-After`, requeue. |
| `INSTITUTION_DOWN` | Skip that account this cycle. No alert unless down > 24h (cross-reference on subsequent run). |
| `ITEM_LOGIN_REQUIRED` | SMS + email with re-auth link. Skip account until resolved. |
| Duplicate `plaid_transaction_id` | The `UNIQUE` constraint will error — catch and skip silently (expected on cursor overlap). |
| Network timeout | Retry with backoff. |

### 2.6 Webhook ↔ cron coordination
Both paths call the same `sync_account(bank_account)` function. It's idempotent (cursor-based) and holds an advisory lock per `plaid_item_id` so a webhook-triggered sync and a cron-triggered sync don't race:

```python
async with pg_advisory_lock(hash(item_id)):
    await sync_account(account)
```

### 2.7 Acceptance — QA: *"Plaid sync pulls transactions from all 3 connected accounts successfully"*
- [ ] Link flow completes for Wells Fargo, Amex, PayPal in sandbox.
- [ ] Historical backfill populates `transactions` for all 3 accounts, zero duplicates.
- [ ] Daily sync runs 3 days consecutively with `job_runs.status='success'`.
- [ ] Webhook signature verification passes Plaid's test webhooks and rejects a forged one.
- [ ] Simulated `ITEM_LOGIN_REQUIRED` triggers SMS + email.
- [ ] Re-running backfill is a no-op (no duplicates, cursor unchanged beyond any new activity).
- [ ] Concurrent webhook + cron does not double-insert (advisory lock verified).

---

## Milestone 3 — Normalization pipeline

**Duration:** 3–4 days · **Dependencies:** M2

Populates `vendor_name_clean` and `description_clean` on incoming transactions. **Pure Python, no AI**, except the optional description cleaner fallback.

### 3.1 Vendor name cleaner (`src/zalazar/normalizer.py`)
Deterministic regex pipeline. Unit tested against a fixture of 50+ real transaction descriptions.

Strip patterns (apply in order):
1. Payment processor prefixes: `SQ *`, `SQ`, `PAYPAL *`, `PP*`, `PYPL`, `VENMO`, `ZELLE`, `CASH APP`, `CA*`, `GOOGLE *`, `APPLE.COM/BILL`
2. Marketplace prefixes: `AMZN MKTP`, `AMZN Mktp`, `AMAZON.COM`, `TST*` (Toast), `TRP*`, `DD *` (DoorDash), `UBR*`, `LYFT*`
3. Trailing reference tails: `\*[A-Z0-9]{4,}$`, 10+ digit numeric runs
4. Trailing location tokens: `, [A-Z]{2}$` (state), known city names
5. Normalize: collapse whitespace, title-case, strip non-printable

```python
def clean_vendor(raw: str) -> str:
    """Pure function. Input: raw Plaid description. Output: cleaned merchant."""
    ...
```

### 3.2 Description cleaner
If raw description is intelligible (≥ 2 real English words, limited symbols), copy raw → clean.
If not, call OpenAI once (cached by SHA256 of raw), prompt:
```
Rewrite this bank transaction description as a short human-readable phrase.
Keep it factual. Do not invent merchants or amounts. Max 80 characters.
Raw: "{description_raw}"
```
Cache stored in a simple `description_cache` table (key = sha256, value = clean text) or Redis if already available.

### 3.3 Amount sign convention
Plaid convention: **positive = outflow, negative = inflow** (counter-intuitive). Your schema uses the standard accounting convention: **positive = inflow (income), negative = outflow (expense)**.

In the ingestion pipeline, invert the sign once:
```python
amount = -plaid_tx.amount  # Plaid → Zalazar convention
```
Document this with a large comment in the sync code. Future engineers will trip on it otherwise.

### 3.4 Type inference
Set `transactions.amount` sign, infer `type` from:
- `amount > 0` → income candidate
- `amount < 0` → expense candidate
- Transfer detection happens separately in M3.5

### 3.5 Transfer pair detection
Runs after sync, before classification. Uses `transactions.paired_transaction_id`:

```python
def find_transfer_pairs(entity_id: UUID, window_days: int = 2):
    """
    For each uncategorized transaction, look for an opposite-sign same-magnitude
    transaction on a different account_id of the same entity within window_days.
    If found: pair them, mark both `excluded`, set paired_transaction_id mutually.
    """
```

Tolerance: exact match on `abs(amount)` to the cent. Timing window: ±2 days.

Edge case: if three or more candidates match (two different transfers of identical amounts), flag all involved for manual review — do not guess.

### 3.6 Acceptance
- [ ] `clean_vendor()` unit tests pass for 30+ documented raw descriptions.
- [ ] Description cleaner caches by hash (OpenAI called once per unique raw).
- [ ] Sign inversion test: a $50 Plaid outflow becomes `amount = -50.00` in the DB.
- [ ] Transfer detection pairs a round-trip Wells Fargo → PayPal correctly, both marked `excluded`, both have `paired_transaction_id` set.
- [ ] Running the pipeline twice on the same Plaid payload is a no-op (idempotent).

---

## Milestone 4 — Categorization engine

**Duration:** 1 week · **Dependencies:** M3

### 4.1 The state machine

```
                    ┌──────────────────┐
                    │ pending_review   │  (fresh from Plaid)
                    └────────┬─────────┘
                             │
                  ┌──────────┴─────────┐
                  │ vendor_rules match │
                  └──────────┬─────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   rule confidence ≥ 0.95  no rule or < 0.95  transfer detected
         │                   │                   │
         ▼                   ▼                   ▼
   auto_categorized    call OpenAI          excluded
   + allocations       (ai_raw_response)    + paired_transaction_id
         │                   │
         │         ┌─────────┴──────────┐
         │         ▼                    ▼
         │   confidence 0.70-0.94  confidence < 0.70
         │         │                    │
         │         ▼                    ▼
         │   ai_suggested           flagged
         │   (no allocations yet)   (no allocations)
         │
         └──→ appears in P&L ──→ reports refresh
```

### 4.2 Rule matching (`src/zalazar/classifier.py`)

```python
async def match_rule(vendor_clean: str, description_clean: str) -> Optional[VendorRuleMatch]:
    """
    Trigram-indexed search on vendor_rules.pattern.
    Returns highest-confidence match or None.
    """
    query = """
        SELECT id, pattern, account_id, default_property_id, confidence,
               property_attribution, match_type
        FROM vendor_rules
        WHERE is_active = TRUE
          AND (
              (match_type = 'exact'    AND pattern = $1)
           OR (match_type = 'contains' AND $1 ILIKE '%' || pattern || '%')
           OR (match_type = 'regex'    AND $1 ~* pattern)
          )
        ORDER BY confidence DESC, LENGTH(pattern) DESC
        LIMIT 1
    """
```

Tie-breaker: longer pattern wins (more specific). A rule matching "home depot 4455 main st" beats a generic "home depot" rule.

If rule match confidence ≥ 0.95 AND `account_id IS NOT NULL` AND (property attribution resolvable):
- Set `transactions.account_id = rule.account_id`
- Set `status = 'auto_categorized'`
- Call the allocator (M5) — must produce allocations summing to `amount` or the DB trigger will reject the write.

If rule match but property attribution is `requires_review` or unresolvable: status stays `ai_suggested` or goes to `flagged`. The rule provides the category; the property still needs human input.

### 4.3 AI classification
Only reached when no rule matches with confidence ≥ 0.95.

- Model: `gpt-4.1-mini` (cost-optimized).
- Temperature: 0.
- Structured output (JSON schema enforced via OpenAI response_format):

```python
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "classification",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "account_code": {"type": "string", "enum": LEAF_ACCOUNT_CODES},
                "confidence_category": {"type": "number", "minimum": 0, "maximum": 1},
                "property_hint": {"type": ["string", "null"]},
                "confidence_property": {"type": "number", "minimum": 0, "maximum": 1},
                "reasoning": {"type": "string", "maxLength": 200}
            },
            "required": ["account_code", "confidence_category", "property_hint", "confidence_property", "reasoning"],
            "additionalProperties": False
        }
    }
}
```

- System prompt: contains the full chart of accounts (leaf accounts only, by `code` + name + description), few-shot examples, and the rule *"If uncertain, return a confidence below 0.70 — it will be flagged for human review."*
- User message: `vendor_name_clean`, `description_clean`, `amount`, `date`, `bank_account.account_name`, and the list of property names/cities/streets for context.

On response:
- Store entire response in `transactions.ai_raw_response` (JSONB).
- Set `categorization_method = 'ai'`, `categorization_reason = reasoning`.
- If `confidence_category >= 0.70` → `status = 'ai_suggested'`, **do not write allocations yet** (schema forbids it for ai_suggested).
- If `< 0.70` → `status = 'flagged'`.

### 4.4 Cost controls
- Batch: if 20+ transactions pending classification, use OpenAI Batch API (24-hour SLA, 50% discount). Acceptable because classification is not real-time-critical — next morning is fine.
- Real-time path (webhook-triggered sync during the day): concurrent async calls, up to 5 at a time.
- Budget alarm: if month-to-date OpenAI spend > $50, email Trilles. Expected steady-state ≪ $10/mo.

### 4.5 QA fixture — the 80% target
Build `tests/fixtures/qa_transactions.json`:
```json
[
  {
    "vendor_raw": "THE HOME DEPOT #4455 ATLANTA GA",
    "description_raw": "PURCHASE",
    "amount": -247.83,
    "date": "2025-09-15",
    "account_name": "Wells Fargo Business Checking",
    "expected_account_code": "EXP-REPAIRS",
    "expected_property_allocation": [{"property_name": "123 Oak St", "percentage": 100}],
    "notes": "Atlanta HD close to 123 Oak St; clear attribution"
  },
  ...
]
```
50+ entries, drawn from actual historical transactions across all three accounts. Include edge cases: mortgage payments, utility bills, ambiguous vendors, transfers, multi-property expenses.

`scripts/run_qa.py` runs the full pipeline and reports:
- Overall classification accuracy
- `auto_categorized` rate (the key number — this is "80% automatic")
- Confusion matrix by account
- Per-account precision/recall
- Saved to `qa_report_YYYYMMDD.md`

### 4.6 Seeding vendor_rules from historical
Because only rule-matched transactions become `auto_categorized`, the 80% target is impossible without a pre-seeded rule base. Run `scripts/seed_vendor_rules.py` after backfill:

1. Cluster historical transactions by `vendor_name_clean` (after normalization).
2. For vendors with ≥ 3 historical occurrences all sharing the same manual category:
   - Create a `vendor_rules` row with `confidence=0.95`, `match_type='contains'`, `source='import'`, `pattern=vendor_name_clean.lower()`.
3. For vendors with clear property attribution (always to same property): set `default_property_id` + `property_attribution='direct'`.
4. Print summary: "Seeded N rules covering X% of historical transaction volume."

This is the move that makes the 80% QA target achievable on Day 1.

### 4.7 Acceptance — QA: *"Categorisation accuracy measured on a set of 50+ known transactions — target 80%+ automatic"*
- [ ] QA script runs end-to-end.
- [ ] After rule seeding, ≥ 80% of QA set reaches `status='auto_categorized'` with correct account.
- [ ] AI-classified transactions all land in `ai_suggested` or `flagged`, never in `auto_categorized`.
- [ ] Every AI call logs full response to `ai_raw_response`.
- [ ] Trigram index used (`EXPLAIN ANALYZE` confirms GIN scan, not seq scan, on rule lookup).
- [ ] Cost: average ≤ $0.005 per AI-classified transaction.

---

## Milestone 5 — Property allocation engine

**Duration:** 4–5 days · **Dependencies:** M4

This is the "property tagging engine" from §11.5, but elevated because your schema supports multi-property allocation. The allocator produces one or more `transaction_allocations` rows whose `amount`s sum to the transaction's `amount`.

### 5.1 Three-layer allocation (`src/zalazar/allocator.py`)

```python
@dataclass
class AllocationDecision:
    allocations: list[AllocationRow]   # 1+ rows, sum must equal tx.amount
    method: allocation_method           # 'direct', 'even_split', 'custom'
    confidence: float                   # 0.0 - 1.0
    reasoning: str

async def allocate(tx: Transaction) -> Optional[AllocationDecision]:
    # Layer 1: address keyword match (single property, direct)
    decision = match_by_address(tx)
    if decision and decision.confidence >= 0.75:
        return decision

    # Layer 2: vendor_rules with property_attribution
    decision = match_by_vendor_rule(tx)
    if decision and decision.confidence >= 0.75:
        return decision

    # Layer 3: bank_accounts.default_property_id
    decision = match_by_account_default(tx)
    if decision:
        return decision  # capped at confidence = 0.75

    return None  # flagged, needs human
```

### 5.2 Layer 1 — address match
Build a property lookup table at process startup:

```python
{
  property_id: {
    "street_number": "123",
    "street_tokens": ["oak", "street"],
    "city_tokens": ["atlanta"],
    "zip": "30301",
    "full_name_tokens": ["123", "oak", "street", "atlanta"]
  },
  ...
}
```

Score function:
- Street number + street name both present → confidence 0.95
- Street name + city → 0.85
- Street name alone → 0.75
- Zip alone → 0.70
- City alone → 0.50 (below threshold — ignored)

Produces **direct** allocation (100% to that property).

### 5.3 Layer 2 — vendor rules
Query `vendor_rules` where `default_property_id IS NOT NULL` and pattern matches. Use the rule's `property_attribution`:
- `direct` → 100% to `default_property_id`
- `even_split` → equal share to all active properties of the entity
- `requires_review` → **no allocation**; transaction goes to ai_suggested/flagged

### 5.4 Layer 3 — bank account default
If the bank account is dedicated to one property (e.g., a PayPal tied to a specific rental), `bank_accounts.default_property_id` applies. Confidence capped at 0.75 — it's a default, not proof, and the user can override in review.

### 5.5 Even-split mechanics
For a shared expense (e.g., bulk insurance covering 4 properties):

```python
def even_split(amount: Decimal, property_ids: list[UUID]) -> list[AllocationRow]:
    n = len(property_ids)
    per = (amount / n).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
    allocations = [AllocationRow(property_id=pid, amount=per, percentage=100/n)
                   for pid in property_ids]
    # Adjust last allocation for rounding residue so sum equals amount exactly
    residue = amount - (per * n)
    allocations[-1].amount += residue
    return allocations
```

This is required because the DB trigger enforces `sum(allocations) == tx.amount` to the cent.

### 5.6 Custom allocation (v2 — manual only)
`allocation_method='custom'` is set when the user manually splits in the review UI (e.g., "this $4,000 roof repair is 60% for 123 Oak and 40% for 456 Maple"). The UI posts percentages; the backend computes amounts with the same rounding trick above.

### 5.7 Acceptance — QA: *"Property tagging accuracy measured on same set — document results"*
- [ ] QA harness reports allocation accuracy per layer.
- [ ] Results documented in `qa_report_YYYYMMDD.md`, committed to repo for historical comparison.
- [ ] Layer 1 confidence calibrated: ≥ 90% of ≥0.75-confidence address matches are correct.
- [ ] Even-split rounding: 4-way split of $100 produces allocations summing to exactly $100.00.
- [ ] Allocation insert rejected by DB trigger if sum ≠ amount (negative test).

---

## Milestone 6 — Review queue + mortgage splitter

**Duration:** 1.5 weeks · **Dependencies:** M4, M5

### 6.1 API surface (FastAPI routes under `/queue`)

```
GET    /queue                         → paginated list: ai_suggested + flagged + pending_review
GET    /queue/{tx_id}                 → full detail + ai_raw_response + suggested allocations
POST   /queue/{tx_id}/approve         → accept AI suggestion as-is: writes allocations, status → reviewed
POST   /queue/{tx_id}/correct         → body: {account_id?, allocations?, reason?}
POST   /queue/{tx_id}/mark-transfer   → status → excluded, finds and pairs counterpart
POST   /queue/{tx_id}/split-mortgage  → see §6.3
POST   /queue/bulk-approve            → body: [{tx_id, ...}]
```

### 6.2 Correction flow — the learning loop
On `POST /queue/{tx_id}/correct`:

1. **Write `audit_log`** with before/after JSON of the transaction and allocations.
2. **Update transaction**: new `account_id`, `status='reviewed'`, `reviewed_by`, `reviewed_at`.
3. **Replace allocations**: delete existing allocations for this tx, insert the new ones. Deferred trigger verifies sum.
4. **Refresh materialized view** (async, debounced): any correction marks the period's monthly P&L stale via existing triggers; schedule a concurrent refresh within 5 minutes.
5. **Create/reinforce vendor_rule:**
   - If existing active rule matches this vendor pattern:
     - If correction *confirms* the existing rule → raise `confidence` by 0.02 (capped at 1.00).
     - If correction *contradicts* the existing rule → drop `confidence` by 0.15 (floor at 0.50). If it drops below 0.70, set `is_active=FALSE`.
   - If no existing rule:
     - Create new rule: `pattern = vendor_name_clean.lower()`, `match_type='contains'`, `confidence=0.95`, `source='ai_correction'`, `account_id=<corrected>`, `default_property_id=<corrected if single-property>`, `property_attribution=direct|even_split|requires_review` based on the correction shape.

The upshot: every human correction makes the next similar transaction `auto_categorized` automatically.

### 6.3 Mortgage payment splitter
Per your schema comment, a mortgage payment from Plaid must become 2–3 records:
- **Original Plaid transaction** → status `excluded`, don't hit P&L.
- **Interest portion** → new transaction, `account_id = INT-MORTGAGE` (property_cost, is_pnl=TRUE), allocated to the property.
- **Principal portion** → new transaction, `account_id = CAP-PRIN` (capital_non_expense, is_pnl=FALSE), allocated to the property.
- **Escrow portion** → `escrow_movements` row, `movement_type='contribution'`.

For v1, this is **human-driven in the review UI**:
- Detection: if `vendor_name_clean` matches a known mortgage servicer pattern (Lima One, Quicken, Mr. Cooper, etc.), the review UI highlights the transaction and shows a "Split mortgage" button.
- The user enters interest/principal/escrow from the mortgage statement (or zero for interest-only loans per your note about Lima One #119434).
- Backend creates the child transactions + escrow movement in a single DB transaction.

For v2 (out of scope here), hook in the per-loan amortization schedule to auto-split.

```python
@router.post("/queue/{tx_id}/split-mortgage")
async def split_mortgage(tx_id: UUID, payload: MortgageSplitIn):
    async with db.transaction():
        original = await get_transaction(tx_id)
        assert payload.interest + payload.principal + payload.escrow == abs(original.amount)

        # Original → excluded
        await update_tx(tx_id, status='excluded', categorization_reason='mortgage parent')

        # Interest child (if non-zero)
        if payload.interest > 0:
            interest_tx = await insert_tx(
                entity_id=original.entity_id,
                bank_account_id=original.bank_account_id,
                transaction_date=original.transaction_date,
                description=f"[Interest] {original.description}",
                amount=-payload.interest,
                account_id=INT_MORTGAGE_ACCOUNT_ID,
                status='reviewed',
                categorization_method='manual',
            )
            await insert_allocation(interest_tx.id, payload.property_id, -payload.interest, 'direct')

        # Principal child (if non-zero — interest-only loans set this to 0)
        if payload.principal > 0:
            principal_tx = await insert_tx(
                ..., amount=-payload.principal, account_id=PRIN_REDUCTION_ACCOUNT_ID, ...
            )
            await insert_allocation(principal_tx.id, payload.property_id, -payload.principal, 'direct')

        # Escrow → escrow_movements (not P&L)
        if payload.escrow > 0:
            await insert_escrow_movement(
                entity_id=original.entity_id,
                loan_account_number=payload.loan_account_number,
                movement_date=original.transaction_date,
                movement_type='contribution',
                amount=payload.escrow,
                property_id=payload.property_id,
            )

        await audit_log(entity_type='transaction', entity_id=tx_id, action='updated',
                        reason='mortgage_split', changed_by=user)
```

### 6.4 Dashboard UI
Minimal: FastAPI + Jinja2 + htmx for interactivity. No React needed for one-user internal tooling.

Queue list page shows:
- Grouped by `status` (ai_suggested first, then flagged, then pending_review that somehow lingered).
- Each row: date, vendor, amount, AI-suggested account, AI-suggested allocation, confidence, action buttons.
- Inline edit for account (searchable dropdown by code/name) and allocation (property + amount/percentage).
- Receipt upload → `supabase.storage`, URL saved to transaction.

### 6.5 Acceptance — QA: *"Review queue tested end-to-end: item appears, client corrects, vendor_patterns updated, future similar transaction auto-approved"*
- [ ] `ai_suggested` transaction appears in queue within 30 seconds of ingestion.
- [ ] Manual correction via UI writes `audit_log`, replaces allocations, creates/updates `vendor_rules`.
- [ ] Subsequent sync containing the same vendor → new transaction lands in `auto_categorized`, skipping the queue.
- [ ] Bulk approve 20 items completes under 2 seconds.
- [ ] Mortgage splitter: $2,500 payment splits into $1,800 interest + $500 principal + $200 escrow; original `excluded`, escrow row created, allocations sum correctly.
- [ ] Attempting to approve an `ai_suggested` transaction without writing allocations fails with the DB trigger error (defense in depth test).

---

## Milestone 7 — Reconciliation engine

**Duration:** 3–4 days · **Dependencies:** M2, M6

### 7.1 Daily reconciliation job
APScheduler cron, `hour=7, minute=0` (after daily sync). For each active `bank_accounts` row:

```python
async def reconcile_account(account):
    plaid_balance = await plaid.get_current_balance(account)

    calculated = await db.execute("""
        SELECT COALESCE(opening_balance, 0) + COALESCE(SUM(amount), 0)
        FROM bank_accounts ba
        LEFT JOIN transactions t ON t.bank_account_id = ba.id
           AND t.status IN ('auto_categorized', 'reviewed', 'excluded')
        WHERE ba.id = $1
        GROUP BY ba.id
    """, account.id)

    diff = plaid_balance - calculated
    settings = await get_notification_settings(account.entity_id)
    tolerance = settings.reconciliation_tolerance  # default $0.01

    status = 'matched' if abs(diff) <= tolerance else 'flagged'

    recon = await insert_reconciliation_log(
        reconciliation_date=today,
        bank_account_id=account.id,
        entity_id=account.entity_id,
        plaid_balance=plaid_balance,
        calculated_balance=calculated,
        difference=diff,
        status=status,
    )

    if status == 'flagged':
        await notifier.send(
            entity_id=account.entity_id,
            type='reconciliation_mismatch',
            channel='both',
            related_reconciliation_id=recon.id,
            context={...},
        )
```

### 7.2 Opening balance
First reconciliation after backfill has no opening balance. Back-solve and store:
```
opening_balance = current_plaid_balance - sum(all_backfilled_transactions)
```
Add `bank_accounts.opening_balance NUMERIC(14,2)` as a small migration if you want to track it explicitly (optional — could also just store in `bank_accounts.notes` if you prefer not to alter the schema).

### 7.3 Weekly summary email
Monday 6:00 AM job. Pulls from `reconciliation_log` and sends a formatted HTML email via Gmail API:
- Per-account status (last 7 days)
- Transactions synced this week
- Current review queue depth
- Any unresolved flagged reconciliations with age

### 7.4 Acceptance — QA: *"Auto-reconciliation tested against known balance figures from actual bank statements"*
- [ ] Reconciliation run against 3 actual statement-period balances (one per institution). Differences documented.
- [ ] Simulated missing transaction → `flagged` status with `difference` exactly equal to the missing amount.
- [ ] `notification_log` row created for each `flagged` reconciliation.
- [ ] Manually resolve a flagged row → status transitions to `resolved` (future migration adds this if needed) or `matched` via note.
- [ ] Weekly summary delivered Monday 6 AM to client's email address.

---

## Milestone 8 — Monthly P&L refresh + reports

**Duration:** 2–3 days · **Dependencies:** M4, M5

This replaces the daily_summaries engine from the spec with the materialized view already in your schema.

### 8.1 Scheduled refresh
APScheduler cron, `hour=7, minute=30`:
```python
@scheduler.scheduled_job('cron', hour=7, minute=30, id='refresh_monthly_pnl')
async def refresh_monthly_pnl():
    run = await job_runs.start('refresh_monthly_pnl')
    try:
        await db.execute("SELECT refresh_monthly_pnl()")
        await job_runs.finish(run, 'success')
    except Exception as e:
        await job_runs.finish(run, 'failed', error=str(e))
        raise
```

### 8.2 On-demand refresh after correction
When a user corrects a transaction in review, the existing triggers flip `is_stale=TRUE` on affected `generated_reports` rows. A debounced background task kicks a concurrent refresh of `monthly_property_pnl` within 5 minutes of the correction. Debouncing avoids refresh thrash during active review sessions.

```python
# Called after every correction; debounced via in-memory lock
async def maybe_refresh_monthly_pnl():
    if already_scheduled_within(minutes=5):
        return
    asyncio.create_task(delayed_refresh(delay_seconds=300))
```

### 8.3 Report generation endpoint
```
GET  /reports/monthly-pnl?property_id=...&period_start=...&period_end=...
GET  /reports/portfolio?period_start=...&period_end=...
POST /reports/generate  → inserts a snapshot into generated_reports with is_stale=FALSE
```

Monthly P&L query hits the materialized view. Portfolio query aggregates across view rows. Both are fast (< 100 ms).

### 8.4 Acceptance — QA: *"Daily calculation engine verified: per-property and portfolio totals match manual sum"*
- [ ] Pick one property + one month. Manually sum `transaction_allocations` joined to `transactions` for `status IN ('auto_categorized','reviewed')`. Compare to `monthly_property_pnl`. Match to the cent.
- [ ] Portfolio total = sum of property rows for the entity + period.
- [ ] Correction to a transaction triggers a refresh within 5 minutes; view reflects the new numbers.
- [ ] Transfer transactions (status `excluded`) do not appear in income or expense totals.
- [ ] `generated_reports.is_stale` flips correctly on both transaction and allocation mutations (trigger test).

---

## Milestone 9 — Notifications

**Duration:** 4–5 days · **Dependencies:** M2, M7, M8

### 9.1 Unified dispatcher
`src/zalazar/notifier/dispatch.py`:

```python
async def send(
    entity_id: UUID,
    type: notification_type,
    channel: notification_channel,
    context: dict,
    related_transaction_id: UUID | None = None,
    related_reconciliation_id: UUID | None = None,
    related_property_id: UUID | None = None,
):
    settings = await get_notification_settings(entity_id)
    if not _is_enabled(settings, type):
        return  # suppressed by settings

    body = render_template(type, context)
    subject = _subject_for(type, context) if channel in ('email', 'both') else None

    log = await insert_notification_log(
        entity_id=entity_id, notification_type=type, channel=channel,
        recipient=_recipient_for(settings, channel), subject=subject, body=body,
        payload=context,
        related_transaction_id=related_transaction_id,
        related_reconciliation_id=related_reconciliation_id,
        related_property_id=related_property_id,
        status='pending',
    )

    try:
        if channel in ('sms', 'both'):
            msg_id = await sms.send(settings.sms_recipient, body)
            await update_log(log.id, status='sent', provider='twilio', provider_message_id=msg_id, sent_at=now())
        if channel in ('email', 'both'):
            msg_id = await email.send(settings.email_recipient, subject, body)
            await update_log(log.id, status='sent', provider='gmail', provider_message_id=msg_id, sent_at=now())
    except Exception as e:
        await update_log(log.id, status='failed', error=str(e))
        raise
```

### 9.2 The five notification types

| Type | Trigger | Channel | Timing | Template vars |
|---|---|---|---|---|
| `large_expense` | On classification, if `amount < -settings.large_expense_threshold` and status ∈ auto_categorized/reviewed | sms | Immediate | vendor, amount, property, date |
| `uncategorized` | Hourly job sweeps `status='flagged'` older than 1 hour | sms | ≤ 1h | vendor, amount, reason |
| `income_received` | On classification of `income` type, status auto_categorized/reviewed | sms | Immediate | source, amount, property |
| `cash_flow_change` | Daily after M8 refresh: compare current month MTD to prior day's MTD per property, alert if Δ% > settings.cash_flow_change_pct | sms | Daily 7:45 | property, delta %, old, new |
| `reconciliation_mismatch` | On M7 `flagged` insert | both | Immediate | account, difference, date |

Thresholds all live in `notification_settings`, per-entity, not hard-coded.

### 9.3 Throttling
- SMS: max 10 per hour per recipient. If breached, digest subsequent alerts into an hourly summary.
- `large_expense`: if > 5 trigger in 10 min, digest.
- `income_received`: muted between 10 PM and 7 AM (context saved, sent as 7 AM digest).

All throttling decisions written to `notification_log.status = 'suppressed'` with a `payload.reason`.

### 9.4 Delivery webhooks
- Twilio status callbacks → `POST /twilio/webhook/status`. Update `notification_log.status` (`sent` → `delivered` / `failed`).
- Gmail doesn't give delivery receipts easily; `sent_at` is the best we get. That's fine for this use case.

### 9.5 Acceptance — QA: *"All 5 notification types triggered and confirmed delivered"*
- [ ] Each of the 5 types triggered in staging, real SMS/email received and screenshotted.
- [ ] `notification_log` populated with `provider_message_id` and `status='sent'` (then `delivered` after Twilio callback).
- [ ] Throttle test: 15 rapid large expenses → first 5 go through, remainder digested.
- [ ] `notification_settings.notify_large_expense=FALSE` → no alert; log shows `status='suppressed'`.
- [ ] Twilio status webhook updates `delivered_at`.

---

## Milestone 10 — JARVIS Q&A

**Duration:** 1 week · **Dependencies:** M8

### 10.1 Architecture
JARVIS is an OpenAI agent with a fixed tool set. It queries `monthly_property_pnl` and occasionally `transactions` — never does raw SQL from LLM output.

```python
tools = [
    {
        "name": "query_pnl",
        "description": "Monthly P&L for a property or portfolio across a date range.",
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {"type": ["string", "null"]},  # null = portfolio
                "entity_id": {"type": "string"},
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
            },
            "required": ["entity_id", "start_date", "end_date"]
        }
    },
    {
        "name": "query_transactions",
        "description": "List individual transactions matching filters. Use only when P&L summary is insufficient.",
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {"type": ["string", "null"]},
                "entity_id": {"type": "string"},
                "account_code": {"type": ["string", "null"]},
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
                "min_amount": {"type": ["number", "null"]},
                "limit": {"type": "integer", "maximum": 50, "default": 20}
            },
            "required": ["entity_id", "start_date", "end_date"]
        }
    },
    {
        "name": "list_properties",
        "description": "List all active properties for an entity.",
        "parameters": {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]}
    },
    {
        "name": "list_accounts",
        "description": "List the chart of accounts (leaf accounts only).",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "review_queue_count",
        "description": "Return the count of transactions currently in ai_suggested or flagged status.",
        "parameters": {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]}
    }
]
```

Each tool is a parameterized SQL query. No LLM-generated SQL.

### 10.2 Guardrails
- System prompt explicitly states: "Always report the as-of date of the P&L view. If you had to disambiguate (e.g., which property the user meant), mention it in the response."
- Ambiguous questions ("what did I spend last month?") → JARVIS asks which property or confirms "portfolio-wide" first. Do not guess.
- Every answer ends with a source footer:
  > Based on transactions through {latest_reviewed_date}. {N} transactions currently in review — they're not in this total.

### 10.3 Interfaces
- REST: `POST /jarvis/ask` body `{question, conversation_id?}`
- SMS: inbound Twilio webhook `/twilio/webhook/sms` forwards to JARVIS, replies via SMS
- Dashboard chat widget using htmx server-sent events for streaming

### 10.4 Baseline test set — QA: *"JARVIS financial Q&A tested with at least 6 different questions"*
1. "What was my net cash flow across the portfolio last month?"
2. "How much did I spend on repairs at [property name] this year?"
3. "Which property has the highest year-to-date expenses?"
4. "Total rental income from Zalazar Holdings in Q1?"
5. "Show me transactions over $1,000 this month."
6. "How much property tax did I pay last year across the portfolio?"
7. "How many transactions are waiting for my review?"
8. "What's my mortgage interest year-to-date for [property name]?" *(tests the split mortgage accounting — interest should be in P&L, principal should not.)*

### 10.5 Acceptance
- [ ] All 8 questions return numerically correct answers, verified against direct SQL.
- [ ] Source footer appears on every response.
- [ ] Ambiguous question triggers clarifying question, not a guess.
- [ ] Response latency p95 < 8 seconds.
- [ ] Inbound SMS to Twilio number replies via SMS with the answer.

---

## Milestone 11 — QA pass + observability + hardening

**Duration:** 1 week · **Dependencies:** M2–M10

### 11.1 Full QA report — maps to the brief's checklist

Deliverable: `qa_report_v1.md` in repo, signed off before go-live.

- [ ] Plaid sync pulls from all 3 connected accounts successfully (M2 AC).
- [ ] Categorization accuracy ≥ 80% `auto_categorized` on 50+ known transactions (M4 AC).
- [ ] Property allocation accuracy documented per layer on same set (M5 AC).
- [ ] Reconciliation tested against 3 actual bank statements (M7 AC).
- [ ] Review queue end-to-end loop verified: review → correct → vendor_rule → future auto-categorization (M6 AC).
- [ ] Monthly P&L matches manual sum for 1 property + portfolio (M8 AC).
- [ ] All 5 notification types delivered and logged (M9 AC).
- [ ] JARVIS Q&A verified on 8 questions (M10 AC).

### 11.2 Observability
- `structlog` JSON logs → stdout, shipped to Sentry (errors) and a simple log aggregator (loki/papertrail/Better Stack — cheapest option for one-client).
- `GET /health` on both services returns: DB reachable, last sync age, review queue depth, last reconciliation status, error rate (last hour).
- A small Metabase or Grafana dashboard over Supabase reads:
  - `job_runs` — success/fail over time, per job
  - `notification_log` — delivery rate
  - `reconciliation_log` — match rate
  - `transactions` grouped by status — queue depth trend

### 11.3 Security checklist
- [ ] Plaid access tokens: Fernet-encrypted at app layer before hitting DB. Key in secrets manager, rotated docs in runbook.
- [ ] All API endpoints (except Plaid and Twilio webhooks) require bearer auth.
- [ ] Plaid webhooks: JWT signature verified against JWKS.
- [ ] Twilio webhooks: signature verified with Twilio auth token.
- [ ] HTTPS-only (Caddy with Let's Encrypt or Cloudflare in front).
- [ ] Supabase RLS: service role used by app; verify restricted role cannot cross-entity read (when multi-entity v2 lands).
- [ ] `ai_raw_response` JSONB may contain descriptions of real transactions — not PII-free by default. Decision: acceptable because only service role reads it. Note in runbook.
- [ ] DB backups: Supabase PITR enabled + nightly logical dump to client-owned S3.
- [ ] `.env.*` files gitignored, no secrets in commit history (verify with gitleaks scan in CI).

### 11.4 Runbook topics
`RUNBOOK.md` must cover:
- Plaid `ITEM_LOGIN_REQUIRED` recovery
- Re-running a failed daily sync
- Resolving a flagged reconciliation (procedure + sign-off)
- Manual allocation correction via SQL (emergency only)
- Rotating the Fernet key (process + data re-encryption)
- How to add a new bank account mid-stream
- How to mark a mortgage payment for split
- Contact tree for outages (Plaid, OpenAI, Twilio, Supabase)

### 11.5 Acceptance
- [ ] `qa_report_v1.md` completed, all items green.
- [ ] Health dashboards live.
- [ ] Security checklist green.
- [ ] Runbook reviewed by Trilles and client.

---

## Milestone 12 — Production go-live

**Duration:** 3–5 days (after Plaid approval) · **Dependencies:** M11 + Plaid production approval

### 12.1 Cutover checklist
1. [ ] Plaid production approval received.
2. [ ] Production environment variables set (secrets manager populated).
3. [ ] Production Supabase schema applied, seeded with real entities/properties/accounts (chart + bank accounts).
4. [ ] Client re-connects Wells Fargo, Amex, PayPal via production Link flow.
5. [ ] Backfill run on production data.
6. [ ] `scripts/seed_vendor_rules.py` run on production backfill.
7. [ ] QA re-scored against production data — accuracy baseline recorded.
8. [ ] APScheduler worker started, jobs visible in `job_runs`.
9. [ ] **7-day shadow period**: notifications route to Trilles only, not client. Observe accuracy, tune.
10. [ ] Client onboarding session: dashboard + Google Sheets (if kept) + JARVIS walkthrough.
11. [ ] Flip `notification_settings.sms_recipient` and `email_recipient` to client.
12. [ ] Go live.

### 12.2 Post-go-live 30-day monitoring
- Weekly: accuracy, reconciliation status, queue volume, correction rate, notification volume.
- If correction rate on `auto_categorized` is < 5% after 30 days → consider nothing, the system is calibrated.
- If correction rate is > 15% → audit the top-hit vendor rules; downgrade or remove outliers.

### 12.3 Acceptance
- [ ] 7 consecutive days of successful daily sync, reconciliation match, no critical Sentry events.
- [ ] Client signoff after onboarding session.
- [ ] Handoff docs (RUNBOOK, README, architecture diagram, recorded walkthrough) delivered.

---

## Timeline summary

| Milestone | Effort | Parallel? |
|---|---|---|
| M0 — Setup + Plaid submission | 1 week | Plaid review runs in background |
| M1 — Schema verification + job_runs migration | 1–2 days | — |
| M2 — Plaid integration | 1.5 weeks | — |
| M3 — Normalization | 3–4 days | overlap with late M2 |
| M4 — Categorization + vendor rule seeding | 1 week | — |
| M5 — Property allocator | 4–5 days | partial overlap with M4 |
| M6 — Review queue + mortgage splitter | 1.5 weeks | — |
| M7 — Reconciliation | 3–4 days | parallel with M6 |
| M8 — Monthly P&L refresh | 2–3 days | parallel with M7 |
| M9 — Notifications | 4–5 days | — |
| M10 — JARVIS | 1 week | parallel with M9 |
| M11 — QA + hardening | 1 week | — |
| M12 — Go-live | 3–5 days | gated on Plaid production approval |

**Total build time:** ~10–12 weeks.
**Gating external dependency:** Plaid production review.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Plaid production rejection or delay | Medium | Blocks M12 | Submit Day 1; keep development tier fully functional as demo fallback. |
| Vendor rule seeding doesn't yield 80% auto-categorization | Medium | Misses QA target | Set expectation as "80% within 30 days of operation"; acceptable v1 floor is 50% at go-live with auto-climb as corrections accumulate. |
| Mortgage split is manual and error-prone | High | Client frustration | Keep it required manual in v1; schedule v2 to auto-split from amortization schedules per loan. |
| Transfer detection false positives (two unrelated $1,000 round-trips) | Low | P&L corruption | Triple-match case flags all for review rather than guessing (M3.5). |
| OpenAI cost runaway | Low | Budget | Batch API for non-real-time; monthly spend alarm at $50. |
| AI description-cleaner on sensitive descriptions | Low | Privacy | Rate-limit and cache; only invoke when needed; never log raw token in external tools. |
| Materialized view refresh contention during active review | Medium | Stale reports | Debounced refresh + `CONCURRENTLY` to avoid blocking reads. |
| Plaid schema changes | Low | Breakage | Pin SDK version; monitor changelog; fixture-based integration tests. |

---

## Deliberately out of scope for v1

- **Receipt OCR.** Receipt URL stored; extraction is v2.
- **Multi-currency.** USD only.
- **Forecasting.** JARVIS answers about history, not the future.
- **Tax form generation** (actual Schedule E). The leaf-account codes are mapped for this; rendering is v2.
- **Mobile app.** Dashboard is web-responsive only.
- **QuickBooks/Xero write-back.** v2.
- **Multi-tenant RLS.** v1 uses single-entity full access; RLS is enabled but the policy is `USING (TRUE)`. v2 scopes by `entity_id` JWT claim.
- **Automated mortgage amortization splits.** v1 is manual in the review UI.

---

## Handoff artifacts at project close

1. Live production system (`api` + `worker`, Supabase, connected services).
2. GitHub repo: source, migrations (incl. v3_2_job_runs.sql), tests, CI config.
3. `RUNBOOK.md`, `README.md`, `qa_report_v1.md`.
4. One-page architecture diagram.
5. Seed scripts (`seed_vendor_rules.py`, `seed_chart_of_accounts.py`, `seed_entities_properties.py`, `run_qa.py`).
6. 60-minute recorded walkthrough.
7. 30-day post-go-live support window.