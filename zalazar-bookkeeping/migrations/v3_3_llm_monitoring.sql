BEGIN;

CREATE TABLE IF NOT EXISTS llm_usage_log (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider        TEXT            NOT NULL, -- 'gemini', 'openai'
    model           TEXT            NOT NULL,
    prompt_tokens   INT             DEFAULT 0,
    completion_tokens INT           DEFAULT 0,
    total_tokens    INT             DEFAULT 0,
    cost_est        NUMERIC(10,6)  DEFAULT 0,
    context_type    TEXT            NOT NULL, -- 'classification', 'jarvis'
    entity_id       UUID            REFERENCES entities(id),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_created ON llm_usage_log(created_at DESC);

COMMIT;
