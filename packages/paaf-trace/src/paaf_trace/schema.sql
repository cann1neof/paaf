-- SPDX-License-Identifier: Apache-2.0
-- PAAF trace store schema (raw SQL, no ORM — CLAUDE.md).
-- Append-mostly local event log. Four tables:
--   runs       — one row per assistant run (prompts, model, timings, tokens, TTFA).
--   tool_calls — many rows per run (tool name, args, results), FK to runs.
--   turn_legs  — one row per AGENT LEG of a multi-agent turn (MESH-05, OQ-5).
--   handoffs   — one row per handoff ATTEMPT, accepted or rejected (MESH-05).
-- time_to_first_audio is a FIRST-CLASS REAL column (TRACE-03), not derived later.
-- The two mesh tables carry no FOREIGN KEY: the fire-and-forget writer never surfaces
-- lastrowid, so there is no run id to point at (same reason fallback_trail below is
-- denormalized). Correlation is by the engine-generated turn_id instead.

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

-- ---------------------------------------------------------------------------
-- The mesh chain (MESH-05, OQ-5, SC#4). Three properties are deliberate:
--
-- (i)  NEW TABLES, not new columns on `runs`. The store's entire schema step is one
--      executescript() of CREATE TABLE IF NOT EXISTS statements — there is no version
--      table and no migration runner anywhere in the repo. IF NOT EXISTS makes an ADDED
--      COLUMN a silent no-op on a table that already exists, so widening `runs` would
--      work on a fresh DB and drop every mesh write on the DB a user already has
--      (RESEARCH Pitfall 5). A new table, by contrast, is created on reopen.
--
-- (ii) NO FOREIGN KEY to `runs`. The writer is fire-and-forget and never surfaces
--      lastrowid, so no producer can learn the run id to reference — the same
--      documented reason served_by/fallback_trail were denormalized onto `runs` above.
--      PRAGMA foreign_keys=ON stays on and is simply not exercised by these tables.
--      Correlation is by turn_id: an engine-generated uuid4 hex string, never a
--      database-assigned id.
--
-- (iii) THE OBSERVER COLUMNS ARE DECLARED NOW, before the observer exists (plan 04-07),
--      precisely because there is no path to add them later. Every column the phase
--      will ever need is declared up front; unused ones simply stay NULL.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS turn_legs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id           TEXT NOT NULL,  -- engine uuid4 correlating every leg of one turn (MESH-05)
    leg_seq           INTEGER NOT NULL, -- 0-based ordinal of this leg within the turn
    agent             TEXT,     -- which agent was AWAKE for this leg (MESH-05)
    served_by         TEXT,     -- the profile that ACTUALLY served this leg (SC#4)
    fallback_trail    TEXT,     -- JSON list of THIS leg's own hops, per-agent (SC#4)
    started_at        REAL,     -- leg start timestamp
    ended_at          REAL,     -- leg end timestamp
    prompt_tokens     INTEGER,  -- token count for this leg: prompt side
    completion_tokens INTEGER   -- token count for this leg: completion side
);

CREATE TABLE IF NOT EXISTS handoffs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id          TEXT NOT NULL,    -- correlates the attempt to its turn_legs siblings
    seq              INTEGER NOT NULL, -- ordinal of this ATTEMPT within the turn
    from_agent       TEXT,   -- the agent that asked to hand off
    to_agent         TEXT,   -- the target the MODEL named — may be a peer it was never
                             -- allowed to reach, which is exactly why REJECTED attempts
                             -- are recorded here: they produce no `runs` row at all and
                             -- would otherwise be invisible (MESH-05, T-04-07)
    outcome          TEXT,   -- accepted | undeclared_peer | observer_retry
                             -- | observer_reroute | budget_exhausted
    observer_verdict TEXT,   -- approve | generic_retry | reroute; NULL when unobserved (D-07)
    observer_profile TEXT,   -- the profile that served the observer; NULL when unobserved
    rerouted_to      TEXT,   -- the observer's corrected target (D-05)
    detail           TEXT,   -- free text: the rejection message, or the constraint cited
    at               REAL    -- attempt timestamp
);
