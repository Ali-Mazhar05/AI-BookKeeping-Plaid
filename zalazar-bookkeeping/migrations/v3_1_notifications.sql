-- v3_1_notifications.sql
-- Notification infrastructure for the AI Bookkeeping System
BEGIN;

-- 1. Create Enums
DO $$ BEGIN
    CREATE TYPE notification_type AS ENUM (
        'large_expense', 
        'uncategorized', 
        'income_received', 
        'cash_flow_change', 
        'reconciliation_mismatch'
    );
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE notification_channel AS ENUM ('sms', 'email', 'both');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE notification_delivery_status AS ENUM ('pending', 'sent', 'delivered', 'failed', 'suppressed');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- 2. Notification Tables
CREATE TABLE IF NOT EXISTS notification_settings (
    id                          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id                   UUID        NOT NULL REFERENCES entities(id),
    sms_recipient              TEXT,
    email_recipient            TEXT,
    notify_large_expense       BOOLEAN     NOT NULL DEFAULT TRUE,
    large_expense_threshold    NUMERIC(14,2) DEFAULT 1000.00,
    notify_uncategorized       BOOLEAN     NOT NULL DEFAULT TRUE,
    notify_income              BOOLEAN     NOT NULL DEFAULT TRUE,
    notify_cash_flow           BOOLEAN     NOT NULL DEFAULT TRUE,
    cash_flow_change_pct       NUMERIC(5,2)  DEFAULT 20.00,
    reconciliation_tolerance   NUMERIC(14,2) DEFAULT 0.01,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notification_log (
    id                  UUID                        PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id           UUID                        NOT NULL REFERENCES entities(id),
    notification_type   notification_type           NOT NULL,
    channel             notification_channel        NOT NULL,
    recipient           TEXT                        NOT NULL,
    subject             TEXT,
    body                TEXT                        NOT NULL,
    payload             JSONB,
    status              notification_delivery_status NOT NULL DEFAULT 'pending',
    provider            TEXT,                       -- 'ringcentral', 'gmail'
    provider_message_id TEXT,
    error_message       TEXT,
    sent_at             TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ                 NOT NULL DEFAULT NOW()
);

-- 3. Indexes
CREATE INDEX IF NOT EXISTS idx_notification_log_entity_status ON notification_log(entity_id, status);
CREATE INDEX IF NOT EXISTS idx_notification_log_created ON notification_log(created_at DESC);

-- 4. RLS
ALTER TABLE notification_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_full_access" ON notification_settings FOR ALL TO authenticated USING (TRUE);
CREATE POLICY "authenticated_full_access" ON notification_log FOR ALL TO authenticated USING (TRUE);

COMMIT;
