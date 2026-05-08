-- REAL SCHEMA EXTRACTED FROM LIVE DB
BEGIN;

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Custom Enums
DO $$ BEGIN
    CREATE TYPE account_type AS ENUM ('income', 'operating_expense', 'property_cost', 'capital_non_expense', 'transfer', 'other');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE allocation_method AS ENUM ('direct', 'even_split', 'custom', 'manual');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE entity_type AS ENUM ('llc', 's_corp', 'c_corp', 'sole_proprietor', 'partnership');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE movement_type AS ENUM ('contribution', 'disbursement');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE notification_channel AS ENUM ('sms', 'email', 'both');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE notification_delivery_status AS ENUM ('pending', 'sent', 'failed', 'suppressed', 'delivered');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE notification_type AS ENUM ('large_expense', 'uncategorized', 'income_received', 'cash_flow_change', 'reconciliation_mismatch', 'weekly_summary');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE reconciliation_status AS ENUM ('matched', 'flagged', 'pending');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE source_type AS ENUM ('plaid', 'manual_csv', 'manual_pdf', 'manual_entry');
EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN
    CREATE TYPE transaction_status AS ENUM ('pending_review', 'auto_categorized', 'ai_suggested', 'reviewed', 'flagged', 'excluded');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- Table: accounts
CREATE TABLE IF NOT EXISTS accounts (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
code                 text                 NOT NULL,
name                 text                 NOT NULL,
account_type         account_type         NOT NULL,
parent_id            uuid,
is_pnl               boolean              NOT NULL,
is_assignable        boolean              NOT NULL DEFAULT true,
display_order        integer              NOT NULL DEFAULT 0,
notes                text,
created_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: audit_log
CREATE TABLE IF NOT EXISTS audit_log (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
entity_type          text                 NOT NULL,
entity_id            uuid                 NOT NULL,
action               text                 NOT NULL,
before_state         jsonb,
after_state          jsonb,
changed_by           text                 NOT NULL,
reason               text,
created_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: bank_accounts
CREATE TABLE IF NOT EXISTS bank_accounts (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
entity_id            uuid                 NOT NULL,
bank_name            text                 NOT NULL,
account_name         text                 NOT NULL,
account_last4        text,
account_type         text                 NOT NULL DEFAULT 'checking'::text,
plaid_account_id     text,
plaid_item_id        text,
plaid_access_token_encrypted text,
plaid_cursor         text,
plaid_last_error     text,
current_balance      numeric,
last_synced_at       timestamp with time zone,
default_property_id  uuid,
is_active            boolean              NOT NULL DEFAULT true,
created_at           timestamp with time zone NOT NULL DEFAULT now(),
updated_at           timestamp with time zone NOT NULL DEFAULT now(),
source_type          source_type          NOT NULL DEFAULT 'manual_entry'::source_type,
opening_balance      numeric               DEFAULT 0
    ,PRIMARY KEY (id)
    ,CONSTRAINT bank_accounts_plaid_account_id_key UNIQUE (plaid_account_id)
);

-- Table: entities
CREATE TABLE IF NOT EXISTS entities (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
name                 text                 NOT NULL,
legal_name           text                 NOT NULL,
entity_type          entity_type          NOT NULL,
address              text,
ein                  text,
state_of_formation   text,
notes                text,
is_active            boolean              NOT NULL DEFAULT true,
created_at           timestamp with time zone NOT NULL DEFAULT now(),
updated_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: escrow_movements
CREATE TABLE IF NOT EXISTS escrow_movements (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
entity_id            uuid                 NOT NULL,
loan_account_number  text                 NOT NULL,
movement_date        date                 NOT NULL,
movement_type        movement_type        NOT NULL,
amount               numeric              NOT NULL,
property_id          uuid,
related_account_id   uuid,
description          text,
source_document_id   uuid,
created_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: generated_reports
CREATE TABLE IF NOT EXISTS generated_reports (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
property_id          uuid                 NOT NULL,
report_type          text                 NOT NULL,
period_start         date                 NOT NULL,
period_end           date                 NOT NULL,
data                 jsonb                NOT NULL,
generated_at         timestamp with time zone NOT NULL DEFAULT now(),
generated_by         text,
is_stale             boolean              NOT NULL DEFAULT false
    ,PRIMARY KEY (id)
);

-- Table: jarvis_conversations
CREATE TABLE IF NOT EXISTS jarvis_conversations (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
entity_id            uuid,
phone_number         text                 NOT NULL,
message              text                 NOT NULL,
response             text,
metadata             jsonb,
created_at           timestamp with time zone  DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: llm_usage_log
CREATE TABLE IF NOT EXISTS llm_usage_log (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
provider             text                 NOT NULL,
model                text                 NOT NULL,
prompt_tokens        integer               DEFAULT 0,
completion_tokens    integer               DEFAULT 0,
total_tokens         integer               DEFAULT 0,
cost_est             numeric               DEFAULT 0,
context_type         text                 NOT NULL,
entity_id            uuid,
created_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: notification_log
CREATE TABLE IF NOT EXISTS notification_log (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
entity_id            uuid                 NOT NULL,
notification_type    notification_type    NOT NULL,
channel              notification_channel NOT NULL,
recipient            text                 NOT NULL,
subject              text,
body                 text                 NOT NULL,
payload              jsonb,
status               notification_delivery_status NOT NULL DEFAULT 'pending'::notification_delivery_status,
provider             text,
provider_message_id  text,
error                text,
related_transaction_id uuid,
related_reconciliation_id uuid,
related_property_id  uuid,
sent_at              timestamp with time zone,
created_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: notification_settings
CREATE TABLE IF NOT EXISTS notification_settings (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
entity_id            uuid                 NOT NULL,
large_expense_threshold numeric              NOT NULL DEFAULT 500.00,
cash_flow_change_pct numeric              NOT NULL DEFAULT 15.00,
reconciliation_tolerance numeric              NOT NULL DEFAULT 0.01,
sms_recipient        text,
email_recipient      text,
notify_large_expense boolean              NOT NULL DEFAULT true,
notify_uncategorized boolean              NOT NULL DEFAULT true,
notify_income_received boolean              NOT NULL DEFAULT true,
notify_cash_flow_change boolean              NOT NULL DEFAULT true,
notify_reconciliation_fail boolean              NOT NULL DEFAULT true,
created_at           timestamp with time zone NOT NULL DEFAULT now(),
updated_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: properties
CREATE TABLE IF NOT EXISTS properties (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
entity_id            uuid                 NOT NULL,
name                 text                 NOT NULL,
address              text                 NOT NULL,
city                 text                 NOT NULL,
state                text                 NOT NULL,
zip                  text                 NOT NULL,
acquisition_date     date,
current_value        numeric,
loan_balance         numeric,
monthly_rent         numeric,
is_active            boolean              NOT NULL DEFAULT true,
notes                text,
created_at           timestamp with time zone NOT NULL DEFAULT now(),
updated_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: reconciliation_log
CREATE TABLE IF NOT EXISTS reconciliation_log (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
reconciliation_date  date                 NOT NULL,
bank_account_id      uuid                 NOT NULL,
entity_id            uuid                 NOT NULL,
plaid_balance        numeric              NOT NULL,
calculated_balance   numeric              NOT NULL,
difference           numeric              NOT NULL,
status               reconciliation_status NOT NULL,
alert_sent           boolean              NOT NULL DEFAULT false,
alert_sent_at        timestamp with time zone,
notes                text,
created_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: source_documents
CREATE TABLE IF NOT EXISTS source_documents (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
entity_id            uuid,
bank_account_id      uuid,
source_type          source_type          NOT NULL,
filename             text,
storage_path         text,
statement_period_start date,
statement_period_end date,
opening_balance      numeric,
closing_balance      numeric,
transaction_count    integer,
uploaded_by          text,
uploaded_at          timestamp with time zone NOT NULL DEFAULT now(),
parsed_at            timestamp with time zone,
parse_status         text                  DEFAULT 'pending'::text,
parse_error          text,
raw_metadata         jsonb
    ,PRIMARY KEY (id)
);

-- Table: transaction_allocations
CREATE TABLE IF NOT EXISTS transaction_allocations (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
transaction_id       uuid                 NOT NULL,
property_id          uuid                 NOT NULL,
amount               numeric              NOT NULL,
percentage           numeric,
method               allocation_method    NOT NULL,
confidence_property  numeric,
notes                text,
created_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

-- Table: transactions
CREATE TABLE IF NOT EXISTS transactions (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
entity_id            uuid                 NOT NULL,
bank_account_id      uuid,
source_document_id   uuid,
transaction_date     date                 NOT NULL,
posted_date          date,
description          text                 NOT NULL,
description_clean    text,
memo                 text,
amount               numeric              NOT NULL,
vendor_name_raw      text,
vendor_name_clean    text,
reference_number     text,
account_id           uuid,
status               transaction_status   NOT NULL DEFAULT 'pending_review'::transaction_status,
confidence_category  numeric,
confidence_property  numeric,
categorization_method text,
categorization_reason text,
ai_raw_response      jsonb,
plaid_transaction_id text,
plaid_pending        boolean               DEFAULT false,
plaid_category       text,
reviewed_by          text,
reviewed_at          timestamp with time zone,
created_at           timestamp with time zone NOT NULL DEFAULT now(),
updated_at           timestamp with time zone NOT NULL DEFAULT now(),
paired_transaction_id uuid,
merchant_name        text,
payment_channel      text,
iso_currency_code    text,
plaid_category_primary text,
plaid_category_detailed text
    ,PRIMARY KEY (id)
);

-- Table: vendor_rules
CREATE TABLE IF NOT EXISTS vendor_rules (
id                   uuid                 NOT NULL DEFAULT uuid_generate_v4(),
pattern              text                 NOT NULL,
match_type           text                 NOT NULL DEFAULT 'contains'::text,
account_id           uuid,
default_property_id  uuid,
confidence           numeric              NOT NULL,
property_attribution text                 NOT NULL DEFAULT 'requires_review'::text,
source               text                 NOT NULL DEFAULT 'manual'::text,
created_from_transaction_id uuid,
notes                text,
is_active            boolean              NOT NULL DEFAULT true,
created_at           timestamp with time zone NOT NULL DEFAULT now(),
updated_at           timestamp with time zone NOT NULL DEFAULT now()
    ,PRIMARY KEY (id)
);

COMMIT;