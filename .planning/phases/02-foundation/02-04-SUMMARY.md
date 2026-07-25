---
phase: 02-foundation
plan: 04
subsystem: core-config
tags: [config, pydantic-v2, atomic-write, optimistic-concurrency, filelock, reload-tiers, ruamel-yaml]

# Dependency graph
requires:
  - phase: 02-01
    provides: paaf-core package skeleton with pydantic/ruamel.yaml/filelock deps + --disable-socket test default
provides:
  - "paaf_core.config.AppConfig — typed Pydantic v2 root with monotonic revision:int and per-field reload-tier metadata"
  - "paaf_core.config.store — atomic_write_bytes, load_config, write_config, dump_config, ConflictError"
  - "paaf_core.config.reload_tiers — reload_tiers(model_cls) discovery + ReloadTier enum + DEFAULT_TIER"
  - "validate-on-read/write, crash-safe atomic persistence, and stale-write conflict rejection under a filelock"
affects: [02-05 secret store (secret VALUES stay out of AppConfig), later phases reading the config tree]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "atomic durable write: tempfile in same dir -> flush + os.fsync -> os.replace -> directory fsync (Pattern 1)"
    - "optimistic monotonic-revision compare-and-swap wrapped in FileLock so two writers cannot both read rev N (Pattern 2)"
    - "reload-tier metadata via Field(json_schema_extra={'reload_tier': ...}) on the same model the store validates (single source of truth, Pattern 5)"
    - "unannotated fields map to a documented DEFAULT_TIER (RESTART) rather than being omitted, so the tier map is exhaustive"

key-files:
  created:
    - packages/paaf-core/src/paaf_core/config/schema.py
    - packages/paaf-core/src/paaf_core/config/store.py
    - packages/paaf-core/src/paaf_core/config/reload_tiers.py
    - packages/paaf-core/tests/test_config_schema.py
    - packages/paaf-core/tests/test_reload_tiers.py
    - packages/paaf-core/tests/test_atomic_write.py
    - packages/paaf-core/tests/test_revision_conflict.py
  modified:
    - packages/paaf-core/src/paaf_core/config/__init__.py

key-decisions:
  - "AppConfig sets extra='forbid' so unknown keys are rejected on read, strengthening the CORE-01 validation boundary."
  - "dump_config added to store.py (beyond the plan's named surface) so tests and callers can seed a config file without reaching into ruamel internals; kept minimal and round-trips with load_config."
  - "DEFAULT_TIER = RESTART: an unclassified key is treated as restart-only (the conservative choice — nothing is assumed hot-swappable until declared)."

requirements-completed: [CORE-01, CORE-02, CORE-03, CORE-06]

coverage:
  - id: CORE-01
    description: "Typed schema validates on read; invalid value rejected"
    verification:
      - kind: unit
        ref: "test_config_schema.py::test_out_of_range_value_is_rejected + test_mistyped_value_is_rejected (ValidationError)"
        status: pass
    human_judgment: false
  - id: CORE-02
    description: "Atomic crash-safe write (temp+fsync+rename+dirfsync)"
    verification:
      - kind: unit
        ref: "test_atomic_write.py::test_failure_before_rename_leaves_original_intact (os.replace injected to raise; original survives, no temp leftover)"
        status: pass
  - id: CORE-03
    description: "Monotonic revision; stale concurrent write rejected as conflict, file untouched"
    verification:
      - kind: unit
        ref: "test_revision_conflict.py::test_stale_revision_raises_conflict_and_leaves_file_untouched"
        status: pass
  - id: CORE-06
    description: "Every config key's reload tier is discoverable"
    verification:
      - kind: unit
        ref: "test_reload_tiers.py (every field path present, HOT/COLD reported, unannotated->default, all four tiers represented)"
        status: pass

# Metrics
duration: 3min
completed: 2026-07-25
status: complete
---

# Phase 02 Plan 04: Config Subsystem (typed schema, atomic write, revision guard, reload tiers) Summary

**A Pydantic v2 config tree that validates on every read/write (CORE-01), persists atomically so a crash mid-write cannot corrupt it (CORE-02), rejects stale concurrent writes with `ConflictError` under a filelock (CORE-03), and reports each key's reload tier via a discovery function (CORE-06) — every guard proven non-vacuous by a paired negative-control test.**

## Performance

- **Duration:** ~3 min
- **Completed:** 2026-07-25
- **Tasks:** 2 (both TDD: RED → GREEN)
- **Files created:** 7 (1 modified: config/__init__.py)

## Accomplishments

- **Typed schema (CORE-01):** `AppConfig(BaseModel, extra='forbid')` with a monotonic `revision: int` (default 1), a `persona` field, and nested `VoiceConfig`/`ModelConfig` sub-models. Out-of-range (`tts_volume=99`) and mistyped (`temperature="not-a-number"`) values raise `pydantic.ValidationError` — the load-bearing negative control.
- **Reload tiers (CORE-06):** fields carry `Field(json_schema_extra={"reload_tier": ReloadTier.X})` spanning all four tiers (HOT `voice.tts_volume`, COLD `voice.stt_model`, WARM `model.temperature`, RESTART `model.provider`). `reload_tiers(AppConfig)` walks `model_fields` recursively with dotted key paths; unannotated fields (`revision`, `persona`) report `DEFAULT_TIER` (RESTART) so the map is exhaustive.
- **Atomic write (CORE-02):** `atomic_write_bytes` writes a temp file in the same directory, `flush()` + `os.fsync`, `os.replace`, then fsyncs the directory. A test injects an exception at `os.replace` and asserts the original file is byte-for-byte intact with no `.cfg.*` temp leftover.
- **Revision guard (CORE-03):** `write_config` acquires a `FileLock`, reloads the current config, and raises `ConflictError` if `expected_revision` is stale — otherwise bumps the revision and atomic-writes. A stale-write test asserts both the raise AND that the on-disk revision/persona are unchanged. The read-modify-write is inside the lock (the documented anti-pattern — a revision guard without a lock — is avoided).
- **Single source of truth:** reload-tier metadata rides on the same model the store validates; the store imports `AppConfig` directly.

## Task Commits

TDD cycle, each phase committed atomically:

1. **Task 1 RED** — failing schema + reload-tier tests: `0ff9d95` (test)
2. **Task 1 GREEN** — schema.py + reload_tiers.py + config/__init__.py: `c627e6e` (feat)
3. **Task 2 RED** — failing atomic-write + revision-conflict tests: `635737a` (test)
4. **Task 2 GREEN** — store.py + __init__ exports + ruff import-order fixups: `8f52a55` (feat)

## Files Created/Modified

- `config/schema.py` — `ReloadTier(str, Enum)` (HOT/WARM/COLD/RESTART); `VoiceConfig`, `ModelConfig`, `AppConfig` (revision, persona, nested sub-models; `extra='forbid'`).
- `config/store.py` — `atomic_write_bytes`, `load_config`, `dump_config`, `write_config`, `ConflictError`.
- `config/reload_tiers.py` — `reload_tiers(model_cls)`, `DEFAULT_TIER`.
- `config/__init__.py` — re-exports the full config API (modified; top-level `paaf_core/__init__.py` untouched per plan).
- `tests/test_config_schema.py`, `tests/test_reload_tiers.py`, `tests/test_atomic_write.py`, `tests/test_revision_conflict.py` — 16 tests, each guard with a paired negative control.

## Decisions Made

- **`extra='forbid'` on `AppConfig`** — unknown keys are rejected on read, hardening the CORE-01 boundary beyond mere type checking.
- **`dump_config` helper added to store.py** — a small, round-trippable YAML serializer so tests and callers seed a config without reaching into ruamel internals. Complements `load_config`; not a scope expansion.
- **`DEFAULT_TIER = ReloadTier.RESTART`** — an unclassified key is conservatively restart-only; nothing is assumed hot-swappable until explicitly declared.

## Deviations from Plan

None affecting design. One in-scope addition and one lint fixup:

- **[Addition] `dump_config` serializer** — the plan named `atomic_write_bytes`/`load_config`/`write_config`/`ConflictError`; `dump_config` was added as the read-side inverse used by `write_config` and test seeding. Documented above.
- **[Lint] ruff import-order** — `ruff check --fix` reordered imports in the four new test files and `config/__init__.py` (alphabetized `__all__`). Tests re-run green after the fix; folded into commit `8f52a55`.

## Verification

- Config suite: `uv run pytest packages/paaf-core/tests/test_config_schema.py packages/paaf-core/tests/test_reload_tiers.py packages/paaf-core/tests/test_atomic_write.py packages/paaf-core/tests/test_revision_conflict.py -q --disable-socket` → **16 passed**.
- Acceptance greps on `store.py`: `os.replace` ×1, `os.fsync` ×2, `FileLock` present.
- Full workspace regression: `uv run pytest -q` → **21 passed** (no regression to Plans 01–03).
- `ruff check` on all new/modified files → clean.

## Threat Mitigations (from plan threat register)

- **T-02-08 (config corruption on crash):** mitigated — atomic temp+fsync+rename+dirfsync, proven by the injected-failure test.
- **T-02-09 (concurrent config edits clobber):** mitigated — optimistic revision + FileLock, proven by the stale-revision negative control.
- **T-02-10 (invalid config accepted):** mitigated — validate-on-read/write + `extra='forbid'`, proven by the ValidationError negative controls.

No new security surface introduced beyond the plan's threat model. Secret values never enter `AppConfig` (only key references, coordinated with Plan 05).

## Known Stubs

None. `VoiceConfig`/`ModelConfig` are deliberately minimal example sections (two fields each) sufficient to cover all four reload tiers; later phases extend the schema with real keys — this is a schema seed, not a stub blocking the plan's goal.

## Next Plan Readiness

- Plan 05 (secret store) can build against `AppConfig` knowing secret *values* must stay out of the YAML — only key references belong in the schema.
- The config tree is now the durable, validated, crash-safe, concurrency-guarded contract every later phase reads.

## Self-Check: PASSED

- All 7 created files + 1 modified file verified present on disk.
- All four task commits (`0ff9d95`, `c627e6e`, `635737a`, `8f52a55`) verified in git log.
- 16 config tests pass; full workspace suite (21) passes with no regression.

---
*Phase: 02-foundation*
*Completed: 2026-07-25*
