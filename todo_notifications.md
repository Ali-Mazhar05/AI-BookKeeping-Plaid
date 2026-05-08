# Notification Implementation Plan — Zalazar Bookkeeping

This document outlines the complete plan for the notification system, replacing all references to Twilio with **RingCentral** and utilizing the **Gmail API** for email. It covers immediate alerts, daily sync reports, and weekly summaries as per the implementation plan.

## 1. Core Platforms
- **SMS:** RingCentral (via `ringcentral` Python SDK)
- **Email:** Gmail API (via `google-api-python-client`)
- **Note:** All references to Twilio in previous plans are hereby superseded by RingCentral.

## 2. Notification Matrix

| Type | Trigger | Channel | Timing | Content |
| :--- | :--- | :--- | :--- | :--- |
| **Large Expense** | Expense > `large_expense_threshold` (e.g., $1,000) | SMS | Immediate | Vendor, Amount, Property, Date, Dashboard Link |
| **Income Received** | New transaction classified as 'Income' | SMS | Immediate | Source, Amount, Property, Date |
| **Review Required** | Transactions in `flagged` or `ai_suggested` state | SMS | Daily (9 AM) | Count of items waiting, Link to Review Queue |
| **Recon Mismatch** | Plaid balance vs. Calculated balance mismatch | Both | Immediate | Account Name, Difference, Action Required |
| **Cash Flow Change** | Significant MTD Δ% change vs prior period | SMS | Daily (7:45 AM) | Property, Delta %, Old, New |
| **Plaid Auth Alert** | `ITEM_LOGIN_REQUIRED` or `PENDING_EXPIRATION` | Both | Immediate | Account Name, Re-auth Link |
| **Nightly Sync Status** | Completion of `plaid_daily_sync` job | Email | Nightly (post-sync) | Success/Failure, Records processed, Errors if any |
| **Weekly Summary** | Portfolio performance snapshot | Email | Monday (6 AM) | P&L snapshot, Weekly totals, Pending review count |

## 3. Implementation Steps

### Phase 1: Infrastructure & Configuration
- [ ] **Secret Management:** Ensure `RC_CLIENT_ID`, `RC_CLIENT_SECRET`, `RC_JWT`, and `GMAIL_REFRESH_TOKEN` are in `.env` / Doppler.
- [ ] **Unified Dispatcher (`dispatch.py`):**
    - [ ] Finalize `_send_impl` to ensure it only uses `sms.py` (RingCentral) and `email.py` (Gmail).
    - [ ] Verify `notification_log` table tracks `provider='ringcentral'` and `provider='gmail'`.
- [ ] **Templates:** Create/Update Jinja2 templates in `src/zalazar/notifier/templates/`:
    - `large_expense.jinja2` / `.html.jinja2`
    - `income_received.jinja2`
    - `reconciliation_mismatch.jinja2`
    - `daily_sync_status.html.jinja2`
    - `weekly_summary.html.jinja2`

### Phase 2: Nightly Sync & Job Notifications
- [ ] **Nightly Sync Hook:** Update `plaid_daily_sync` job in `worker/jobs.py` to trigger a notification upon completion.
    - [ ] On Success: Send "Sync Successful" with transaction counts.
    - [ ] On Failure: Send "Sync Failed" with error snippets to Admin.
- [ ] **Job Run Monitoring:** Ensure `job_runs` table is updated correctly so notifications can pull accurate metadata.

### Phase 3: Immediate Alerts (Webhooks & Pipeline)
- [ ] **Plaid Webhooks:** Ensure `handle_webhook` in `webhooks.py` calls `dispatch.send` for:
    - `ITEM_LOGIN_REQUIRED`
    - `PENDING_EXPIRATION`
    - `USER_PERMISSION_REVOKED`
- [ ] **Classification Pipeline:** Hook `dispatch.send` into the `classifier.py` / `allocator.py` flow for `large_expense` and `income_received`.

### Phase 4: Summaries & Throttling
- [ ] **Weekly Summary Job:** Implement the APScheduler task for Monday mornings.
- [ ] **Throttling Logic:**
    - [ ] SMS: Max 10 per hour per recipient to prevent spam.
    - [ ] Quiet Hours: Delay `income_received` SMS between 10 PM and 7 AM (batching into a morning digest).

## 4. Security & Observability
- [ ] **Audit Trail:** Every notification MUST have a row in `notification_log`.
- [ ] **Error Handling:** If RingCentral or Gmail fails, log the error to Sentry and retry high-priority alerts (Recon Mismatch, Auth Alert) once.
- [ ] **Phone Number Formatting:** Ensure E.164 format for all recipients.

## 5. Success Criteria
- [ ] Nightly sync email arrives with correct stats.
- [ ] SMS alerts arrive on phone within 30 seconds of a $1,000+ test transaction.
- [ ] Re-auth link in SMS leads directly to the Plaid Link reconnection page.
- [ ] Weekly summary email reflects the same P&L as the dashboard.
