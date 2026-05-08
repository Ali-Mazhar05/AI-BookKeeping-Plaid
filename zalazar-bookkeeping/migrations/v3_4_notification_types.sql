-- v3_4_notification_types.sql
-- Adds plaid_auth_alert and nightly_sync_status to the notification_type enum.

ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'plaid_auth_alert';
ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'nightly_sync_status';
