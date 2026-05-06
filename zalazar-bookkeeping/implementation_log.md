# Implementation Log: Production Readiness Roadmap

This log tracks the remaining tasks required to bring the Zalazar Bookkeeping system to a production-ready state, based on the **Production Implementation Plan (v2)**.

## Milestone 0 & 1: Foundation
- [ ] **Production Secrets:** Transition from `.env` to a secrets manager (Doppler/AWS) for the Plaid Fernet key and provider API keys.
- [ ] **CI/CD:** Implement GitHub Actions for automated linting (`ruff`), type-checking (`mypy`), and unit testing on every push.
- [ ] **Environment Parity:** Verify `staging` and `production` Supabase projects are correctly configured with RLS and identical schema versions.

## Milestone 2: Plaid Integration
- [x] **Webhook Signature Verification:** Replace the placeholder in `src/zalazar/plaid/webhooks.py` with real JWT verification using Plaid's JWKS.
- [x] **Advisory Locking:** Implement `pg_advisory_lock` in `sync_account` (updated with stable hash) to prevent race conditions.
- [ ] **Re-auth Flow:** Finalize the UI/UX for the `ITEM_LOGIN_REQUIRED` recovery flow (rendering Link in 'update' mode).

## Milestone 4: Categorization Engine
- [x] **AI Safety Constraint:** Update `classifier.py` to ensure AI classifications **never** set status to `auto_categorized`. They must always be `ai_suggested` for human review.
- [ ] **Historical Rule Seeding:** Execute `scripts/seed_vendor_rules.py` to populate initial high-confidence rules from historical transaction patterns.
- [ ] **Batch API:** Implement OpenAI/Gemini Batch API for background processing to reduce costs.
- [ ] **LLM Spend Monitor:** Set up a budget alarm/threshold for LLM API usage.

## Milestone 6: Review Queue & Mortgage Splitter
- [x] **Learning Loop:** Implement rule reinforcement logic so that human corrections in the Review Queue automatically create or update `vendor_rules`.
- [x] **Audit Trail:** Ensure all manual modifications and mortgage splits are logged to the `audit_log` table with before/after snapshots.
- [x] **Debounced Materialized View Refresh:** Implement the background task to refresh `monthly_property_pnl` 5 minutes after a user finishes a batch of reviews.

## Milestone 7: Reconciliation Engine
- [x] **Opening Balances:** Implement the one-time calculation to back-solve and store the `opening_balance` for newly connected bank accounts.
- [x] **Weekly Summary Job:** Finalize the APScheduler job to send the Monday 6:00 AM financial summary email.

## Milestone 9: Unified Notifications
- [x] **Throttling Logic:** Implement hourly and daily throttles in `dispatch.py` to prevent notification fatigue.
- [x] **Jinja2 Migration:** Move notification bodies from hard-coded strings to Jinja2 templates in `src/zalazar/notifier/templates/`.
- [ ] **Delivery Webhooks:** Implement the Twilio status callback listener to update `notification_log.status` from 'sent' to 'delivered'.

## Milestone 10: JARVIS Q&A
- [x] **Source Footers:** Enforce the "transactions through {date}" footer on all JARVIS responses to ensure data transparency.
- [ ] **SMS Integration:** Connect inbound Twilio SMS webhooks to the JARVIS agent for mobile financial queries.

## Milestone 11: QA & Hardening
- [ ] **Observability:** Connect `structlog` output to a log aggregator (Sentry/Better Stack).
- [x] **Health Checks:** Finalize the `/health` endpoint to report DB connectivity, last sync age, and review queue depth.
- [ ] **Security Audit:** Verify RLS policies and ensure the Plaid Fernet key rotation process is documented in the `RUNBOOK.md`.

## Milestone 12: Go-Live
- [ ] **Shadow Period:** Complete a 7-day shadow period with notifications routed to developers only.
- [ ] **Client Handoff:** Finalize the `RUNBOOK.md` and conduct the onboarding walkthrough.
