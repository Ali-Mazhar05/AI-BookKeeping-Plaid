BEGIN;

-- 1. Create job_status enum
DO $$ BEGIN
    CREATE TYPE job_status AS ENUM ('running', 'success', 'partial', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. Create job_runs table
CREATE TABLE IF NOT EXISTS job_runs (
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

-- 3. Create indexes
CREATE INDEX IF NOT EXISTS idx_job_runs_job_started ON job_runs(job_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_runs_status      ON job_runs(status) WHERE status IN ('running');

-- 4. Enable RLS
ALTER TABLE job_runs ENABLE ROW LEVEL SECURITY;

-- 5. Create policy
DO $$ BEGIN
    CREATE POLICY "authenticated_full_access" ON job_runs FOR ALL TO authenticated USING (true);
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

COMMIT;
