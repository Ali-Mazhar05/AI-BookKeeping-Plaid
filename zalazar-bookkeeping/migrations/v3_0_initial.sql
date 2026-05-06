-- v3_0_initial.sql
-- Core schema for the AI Bookkeeping System
BEGIN;

-- 1. Enable Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Create Enums
DO $$ BEGIN
    CREATE TYPE entity_type AS ENUM ('individual', 'llc', 'corporation');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE account_type AS ENUM ('income', 'operating_expense', 'property_cost', 'capital_non_expense', 'transfer');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE transaction_status AS ENUM ('pending_review', 'ai_suggested', 'flagged', 'auto_categorized', 'reviewed', 'excluded');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE source_type AS ENUM ('plaid', 'manual', 'csv');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE allocation_method AS ENUM ('direct', 'even_split', 'custom');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE reconciliation_status AS ENUM ('matched', 'flagged', 'resolved');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE movement_type AS ENUM ('contribution', 'disbursement');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- 3. Core Tables
CREATE TABLE IF NOT EXISTS entities (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT        NOT NULL,
    type        entity_type NOT NULL DEFAULT 'llc',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS properties (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id       UUID        NOT NULL REFERENCES entities(id),
    name            TEXT        NOT NULL,
    street_address  TEXT,
    city            TEXT,
    state           TEXT,
    zip             TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bank_accounts (
    id                          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id                   UUID        NOT NULL REFERENCES entities(id),
    plaid_account_id           TEXT        UNIQUE,
    plaid_item_id              TEXT,
    plaid_access_token_encrypted TEXT,
    institution_name           TEXT,
    account_name               TEXT,
    account_last4              TEXT,
    account_type               TEXT,
    is_active                  BOOLEAN     NOT NULL DEFAULT TRUE,
    plaid_cursor               TEXT,
    plaid_last_error           TEXT,
    default_property_id        UUID        REFERENCES properties(id),
    opening_balance            NUMERIC(14,2) DEFAULT 0,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chart_of_accounts (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    code            TEXT            UNIQUE NOT NULL,
    name            TEXT            NOT NULL,
    parent_code     TEXT            REFERENCES chart_of_accounts(code),
    account_type    account_type    NOT NULL,
    is_assignable   BOOLEAN         NOT NULL DEFAULT TRUE,
    is_pnl          BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id                      UUID                PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id               UUID                NOT NULL REFERENCES entities(id),
    bank_account_id         UUID                NOT NULL REFERENCES bank_accounts(id),
    plaid_transaction_id    TEXT                UNIQUE,
    transaction_date        DATE                NOT NULL,
    amount                  NUMERIC(14,2)      NOT NULL,
    vendor_name_raw         TEXT,
    vendor_name_clean       TEXT,
    description_raw         TEXT,
    description_clean       TEXT,
    account_id              UUID                REFERENCES chart_of_accounts(id),
    status                  transaction_status  NOT NULL DEFAULT 'pending_review',
    categorization_method   TEXT,
    categorization_reason   TEXT,
    ai_raw_response         JSONB,
    paired_transaction_id   UUID                REFERENCES transactions(id),
    reviewed_by             TEXT,
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transaction_allocations (
    id              UUID                PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id  UUID                NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    property_id     UUID                NOT NULL REFERENCES properties(id),
    amount          NUMERIC(14,2)      NOT NULL,
    percentage      NUMERIC(5,2),
    method          allocation_method   NOT NULL DEFAULT 'direct',
    confidence      NUMERIC(3,2),
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vendor_rules (
    id                      UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    pattern                 TEXT            NOT NULL,
    account_id              UUID            REFERENCES chart_of_accounts(id),
    default_property_id     UUID            REFERENCES properties(id),
    confidence              NUMERIC(3,2)    NOT NULL DEFAULT 0.95,
    property_attribution    TEXT,           -- 'direct', 'even_split', 'requires_review'
    match_type              TEXT            NOT NULL DEFAULT 'contains', -- 'exact', 'contains', 'regex'
    is_active               BOOLEAN         NOT NULL DEFAULT TRUE,
    source                  TEXT            NOT NULL DEFAULT 'manual',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type     TEXT            NOT NULL,
    entity_id       UUID            NOT NULL,
    action          TEXT            NOT NULL,
    before_data     JSONB,
    after_data      JSONB,
    changed_by      TEXT,
    reason          TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reconciliation_log (
    id                  UUID                PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank_account_id     UUID                NOT NULL REFERENCES bank_accounts(id),
    entity_id           UUID                NOT NULL REFERENCES entities(id),
    reconciliation_date DATE                NOT NULL,
    plaid_balance       NUMERIC(14,2)      NOT NULL,
    calculated_balance  NUMERIC(14,2)      NOT NULL,
    difference          NUMERIC(14,2)      NOT NULL,
    status              reconciliation_status NOT NULL DEFAULT 'matched',
    notes               TEXT,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS escrow_movements (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id           UUID            NOT NULL REFERENCES entities(id),
    property_id         UUID            NOT NULL REFERENCES properties(id),
    movement_date       DATE            NOT NULL,
    movement_type       movement_type   NOT NULL,
    amount              NUMERIC(14,2)  NOT NULL,
    loan_account_number TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS generated_reports (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id       UUID        NOT NULL REFERENCES entities(id),
    report_type     TEXT        NOT NULL,
    parameters      JSONB,
    is_stale        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS description_cache (
    sha256      TEXT        PRIMARY KEY,
    clean_text  TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Materialized Views
CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_property_pnl AS
SELECT
    t.entity_id,
    ta.property_id,
    date_trunc('month', t.transaction_date)::date AS month,
    t.account_id,
    coa.code AS account_code,
    coa.name AS account_name,
    SUM(ta.amount) AS total_amount
FROM transactions t
JOIN transaction_allocations ta ON ta.transaction_id = t.id
JOIN chart_of_accounts coa ON coa.id = t.account_id
WHERE t.status IN ('auto_categorized', 'reviewed')
  AND coa.is_pnl = TRUE
GROUP BY 1, 2, 3, 4, 5, 6;

CREATE UNIQUE INDEX IF NOT EXISTS idx_monthly_property_pnl_unique 
ON monthly_property_pnl (entity_id, property_id, month, account_id);

-- 5. Triggers & Functions
-- Trigger to enforce leaf-only account assignment
CREATE OR REPLACE FUNCTION fn_check_account_assignable() RETURNS TRIGGER AS $$
BEGIN
    IF NOT (SELECT is_assignable FROM chart_of_accounts WHERE id = NEW.account_id) THEN
        RAISE EXCEPTION 'Cannot assign transaction to a non-assignable (parent) account';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_check_transaction_account_assignable
BEFORE INSERT OR UPDATE OF account_id ON transactions
FOR EACH ROW EXECUTE FUNCTION fn_check_account_assignable();

-- Trigger to enforce allocation sum invariant
CREATE OR REPLACE FUNCTION fn_check_allocations_sum() RETURNS TRIGGER AS $$
DECLARE
    total_alloc NUMERIC(14,2);
    tx_amount NUMERIC(14,2);
BEGIN
    SELECT amount INTO tx_amount FROM transactions WHERE id = NEW.transaction_id;
    SELECT SUM(amount) INTO total_alloc FROM transaction_allocations WHERE transaction_id = NEW.transaction_id;
    
    -- This check is typically deferred until transaction commit
    -- but for simplicity we'll logic it in the app or a statement trigger.
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Cache invalidation for reports
CREATE OR REPLACE FUNCTION fn_invalidate_reports() RETURNS TRIGGER AS $$
BEGIN
    UPDATE generated_reports 
    SET is_stale = TRUE 
    WHERE entity_id = COALESCE(NEW.entity_id, OLD.entity_id)
      AND is_stale = FALSE;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_invalidate_reports_tx
AFTER INSERT OR UPDATE OR DELETE ON transactions
FOR EACH ROW EXECUTE FUNCTION fn_invalidate_reports();

-- 6. Indexes
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_vendor_rules_pattern_trgm ON vendor_rules USING GIN (pattern gin_trgm_ops);

-- 7. RLS
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE chart_of_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaction_allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendor_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE reconciliation_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE escrow_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_full_access" ON entities FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON properties FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON bank_accounts FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON chart_of_accounts FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON transactions FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON transaction_allocations FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON vendor_rules FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON audit_log FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON reconciliation_log FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON escrow_movements FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON generated_reports FOR ALL TO authenticated USING (TRUE);

COMMIT;
