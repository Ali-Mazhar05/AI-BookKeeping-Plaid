# Zalazar Bookkeeping RUNBOOK

## 1. Plaid `ITEM_LOGIN_REQUIRED` Recovery
If the user's bank requires re-authentication, Plaid triggers the `ITEM_LOGIN_REQUIRED` webhook.
1. The webhook listener sets `is_active = FALSE` and `plaid_last_error = 'ITEM_LOGIN_REQUIRED'` in the `bank_accounts` table.
2. A notification is dispatched via SMS/Email to the client.
3. The client must visit the UI, which will render a new Plaid Link "Update Mode" token using the existing `plaid_access_token`.
4. Upon success, the account is reactivated and syncing resumes.

## 2. Re-running a Failed Daily Sync
If the `plaid_daily_sync` cron job fails (e.g. timeout, 5xx):
1. Check `job_runs` table: `SELECT * FROM job_runs WHERE job_name = 'plaid_daily_sync' ORDER BY started_at DESC LIMIT 1;`
2. If the error is transient, you can manually trigger it:
```bash
docker-compose exec worker python -c "import asyncio; from zalazar.plaid.sync import sync_account; asyncio.run(sync_account('account_id'))"
```
*(Ensure you use the correct `bank_account.id` UUID).*

## 3. Resolving a Flagged Reconciliation
If the daily job flags a mismatch between the calculated DB ledger and Plaid's reported balance:
1. Review the `reconciliation_log` difference amount.
2. Compare the `transactions` in the DB against the raw bank statement for the affected date.
3. Identify the missing, duplicated, or mis-amounted transaction.
4. Correct via SQL or Review Queue UI.
5. Manually mark the reconciliation log status as `resolved`.

## 4. Manual Allocation Correction via SQL (Emergency)
If the UI is down and a critical allocation needs correction:
```sql
BEGIN;
DELETE FROM transaction_allocations WHERE transaction_id = '<tx_id>';
INSERT INTO transaction_allocations (transaction_id, property_id, amount, allocation_method, confidence)
VALUES ('<tx_id>', '<prop_id>', <amount>, 'custom', 1.0);
UPDATE transactions SET status = 'reviewed', categorization_reason = 'manual_sql' WHERE id = '<tx_id>';
COMMIT;
```

## 5. Rotating the Fernet Key
1. Generate a new Fernet key (`cryptography.fernet.Fernet.generate_key()`).
2. Run a script that reads all `bank_accounts.plaid_access_token_encrypted` using the *old* key.
3. Re-encrypt all tokens using the *new* key and `UPDATE` the database.
4. Update the `.env` `PLAID_TOKEN_FERNET_KEY` on the server and restart all containers.

## 6. How to Mark a Mortgage Payment for Split
In the Review Queue UI:
1. Locate the mortgage payment (typically `status = 'ai_suggested'` or `flagged`).
2. Click **Split Mortgage**.
3. Input the Interest, Principal, and Escrow amounts from the statement.
4. The system will automatically exclude the parent transaction and create the child records.

## 7. Contact Tree for Outages
- **Plaid:** Status Page (status.plaid.com). Support tickets via Plaid Dashboard.
- **OpenAI:** Status Page (status.openai.com).
- **RingCentral:** Status Page (status.ringcentral.com).
- **Supabase:** Status Page (status.supabase.com). Support via Supabase dashboard.
- **Primary Developer/Maintainer:** Trilles
