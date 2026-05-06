-- Migration: v3_3_plaid_metadata.sql
-- Add granular Plaid metadata columns to transactions table

ALTER TABLE transactions
ADD COLUMN IF NOT EXISTS merchant_name TEXT,
ADD COLUMN IF NOT EXISTS payment_channel TEXT,
ADD COLUMN IF NOT EXISTS iso_currency_code TEXT,
ADD COLUMN IF NOT EXISTS plaid_category_primary TEXT,
ADD COLUMN IF NOT EXISTS plaid_category_detailed TEXT;

-- Update existing column plaid_pending to match user's requested naming if necessary
-- (Existing column is plaid_pending, which is correct)
