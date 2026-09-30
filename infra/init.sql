-- SurakshaAI schema (CLAUDE.MD §12).
--
-- Runs once on first container boot. There is deliberately no 'submitted'
-- status and no submitted_at column: §2 is a hard rule that the product never
-- files anything, and a column that cannot be set is a column that invites
-- someone to set it.

CREATE TABLE IF NOT EXISTS cases (
    id                  TEXT PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- 'intercept' (Act 1) or 'rescue' (Act 2); scenario is the sandbox clip id.
    act                 TEXT,
    scenario            TEXT,

    -- classify_fraud
    fraud_type          TEXT,
    confidence          REAL,

    -- extract_entities. All nullable on purpose: §10.1 says a field that was
    -- not spoken stays empty and the agent asks for it aloud. A NOT NULL here
    -- would push someone into inventing a default.
    amount              INTEGER,
    app                 TEXT,
    utr                 TEXT,
    when_ago            TEXT,
    district            TEXT,
    suspect_number      TEXT,

    -- Reported per turn by AssemblyAI when language_detection is on.
    language_code       TEXT,
    language_confidence REAL,

    -- Redacted before it ever arrives here (§12 REDACTION IS MANDATORY).
    transcript          JSONB NOT NULL DEFAULT '[]'::jsonb,

    status              TEXT NOT NULL DEFAULT 'drafted'
        CONSTRAINT cases_status_valid
        CHECK (status IN ('drafted', 'documents_ready'))
);

-- Every tool call, with its timing. Drives the tool panel and the forensic
-- record, and is the audit trail behind the latency stats in §17.
CREATE TABLE IF NOT EXISTS tool_events (
    id          SERIAL PRIMARY KEY,
    case_id     TEXT REFERENCES cases(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    args        JSONB NOT NULL DEFAULT '{}'::jsonb,
    result      JSONB NOT NULL DEFAULT '{}'::jsonb,
    ms          INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tool_events_case_id_idx ON tool_events (case_id);
CREATE INDEX IF NOT EXISTS cases_created_at_idx ON cases (created_at DESC);
