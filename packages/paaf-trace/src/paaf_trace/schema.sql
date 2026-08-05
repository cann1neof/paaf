-- SPDX-License-Identifier: Apache-2.0
-- PAAF trace store schema (raw SQL, no ORM — CLAUDE.md).
-- Append-mostly local event log. Two tables:
--   runs       — one row per assistant run (prompts, model, timings, tokens, TTFA).
--   tool_calls — many rows per run (tool name, args, results), FK to runs.
-- time_to_first_audio is a FIRST-CLASS REAL column (TRACE-03), not derived later.

CREATE TABLE IF NOT EXISTS runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prompts             TEXT,      -- the prompt(s) sent to the model (TRACE-02)
    model               TEXT,      -- the selected model identifier (TRACE-02)
    started_at          REAL,      -- run start timestamp (monotonic/epoch seconds)
    ended_at            REAL,      -- run end timestamp
    prompt_tokens       INTEGER,   -- token count: prompt side (TRACE-02)
    completion_tokens   INTEGER,   -- token count: completion side (TRACE-02)
    time_to_first_audio REAL,      -- TTFA in seconds — first-class metric (TRACE-03)
    -- Fallback provenance (MODEL-04, D-06, SC#4). Denormalized onto runs rather than a
    -- child fallbacks table: the fire-and-forget writer never surfaces lastrowid, so an
    -- FK child would force a writer redesign (RESEARCH Pitfall 5). Both are additive and
    -- nullable — a run that never fell back simply leaves them NULL.
    served_by           TEXT,      -- profile name that ACTUALLY served the run (SC#4)
    fallback_trail      TEXT       -- JSON list of fallback hops: [{from,to,reason}]
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id  INTEGER NOT NULL REFERENCES runs(id),  -- FK to the owning run (TRACE-02)
    name    TEXT NOT NULL,   -- tool name invoked
    args    TEXT,            -- serialized call arguments (JSON text)
    results TEXT             -- serialized call results (JSON text)
);
