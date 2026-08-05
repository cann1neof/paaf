---
phase: 03-paaf-llm-core
plan: 03
subsystem: build-guards
tags: [import-linter, ci, architecture-boundary, negative-control, MODEL-08]
requires:
  - ".importlinter (Phase 2, Plan 02) — the three-contract baseline"
  - "tests/negcontrol/ (Phase 2) — the fixture + parametrized red-on-violation harness"
provides:
  - "langchain provider bindings (langchain_ollama/_anthropic/_openai) forbidden framework-wide"
  - "the single permitted edge: paaf_llm._engine (+ submodules) -> langchain*, whitelisted"
  - "langchain-providers-confined-to-adapter negative control proving the extension bites"
affects:
  - "plan 03-08 (real LangChain adapter) — its imports are legal only inside paaf_llm._engine"
tech-stack:
  added: []
  patterns:
    - "import-linter forbidden contract + ignore_imports whitelist, longhand (no partial-segment wildcards)"
    - "negative-control pairing: every contract has a fixture proving it goes red"
key-files:
  created:
    - tests/negcontrol/paaf_llm_provider_violation/__init__.py
  modified:
    - .importlinter
    - tests/negcontrol/.importlinter-negcontrol
    - tests/negcontrol/test_import_boundary.py
decisions:
  - "Whitelist spelled longhand (14 explicit edges) because import-linter 2.13 wildcards replace a WHOLE module segment — `langchain*` is a ValidationError, not a prefix match."
  - "`paaf_llm._engine` listed separately from `paaf_llm._engine.**` because `**` matches strict descendants only; omitting the bare name would leave the real adapter's own `__init__` imports red."
  - "`unmatched_ignore_imports_alerting = warn` (not the default `error`) because the whitelist is laid down ahead of the adapter — every edge is unmatched until plan 03-08 lands."
metrics:
  duration: ~35m
  completed: 2026-08-05
  tasks: 2
  files: 4
status: complete
---

# Phase 3 Plan 03: Import-Linter Provider Boundary Summary

Extended the FOUND-04 import-linter boundary to forbid the three langchain provider
bindings framework-wide and whitelist exactly one importer — `paaf_llm._engine` — with a
paired negative control proving the extension actually turns CI red.

## What Was Built

**Task 1 — the contract extension** (`.importlinter`, commit `0515365`)

`langchain_ollama`, `langchain_anthropic`, and `langchain_openai` joined the
`langchain-confined-to-adapter` contract's `forbidden_modules`. Before this, they were in
**no** forbidden list at all (RESEARCH Pitfall 3) — the framework could have imported a
provider binding anywhere and CI would have stayed green, silently eroding the
swappability guarantee that MODEL-08 rests on.

The one permitted edge is now an explicit `ignore_imports` whitelist naming
`paaf_llm._engine` and `paaf_llm._engine.**` as the only importers, across all seven
forbidden modules.

**Task 2 — the negative control** (commit `b819061`)

`tests/negcontrol/paaf_llm_provider_violation/` imports `langchain_ollama` from outside
the adapter. It is mapped onto a new `langchain_provider` contract in
`.importlinter-negcontrol` and registered as a `VIOLATION_CASES` row, so the existing
parametrized `test_contract_goes_red_on_violation` now proves the provider contract exits
nonzero and names itself.

## Key Decisions

**The plan's shorthand whitelist expression does not parse.** The plan (and the Phase-2
header comment, and the `_engine/__init__.py` marker docstring) all specified the edge as
`paaf_llm._engine.* -> langchain*`. Reading import-linter 2.13's source shows two
independent reasons that exact string cannot work:

1. `ModuleExpressionField.parse` raises `ValidationError("A wildcard can only replace a
   whole module.")` for any segment containing `*` alongside other characters. `langchain*`
   is not a prefix wildcard — each forbidden module must be named in full.
2. `*` and `**` both match **strict descendants**. Verified empirically against grimp:
   `find_matching_modules("paaf_core.**")` does not contain `paaf_core`. Since the adapter's
   own imports will live in `_engine/__init__.py` (module `paaf_llm._engine`), a
   descendants-only expression would have left plan 03-08's adapter red on day one — the
   precise failure this guard exists to prevent, inverted.

The whitelist is therefore 14 explicit lines. Verbose, but every permitted edge is
greppable and the "no broader carve-out" property is visible by inspection.

**Unmatched-alerting relaxed to `warn`.** The default `error` fails a contract when an
`ignore_imports` entry matches nothing. Because this guard is deliberately laid down
*ahead* of the adapter, all 14 entries are currently unmatched. `warn` was chosen over
`none` so stale or typo'd whitelist entries stay visible in CI output rather than rotting
silently. Current output: `langchain-confined-to-adapter KEPT (14 warnings)`.

## Verification Performed

Beyond the plan's two required commands, the whitelist's **permissive** half was proven
directly — the negative control only proves the forbidding half, and a whitelist that has
never been exercised is itself an unverified claim. Using a throwaway package tree in the
scratchpad (no sibling-owned files touched):

| Case | Setup | Result |
|------|-------|--------|
| A | `_engine/__init__.py` and `_engine/deep.py` import providers | `KEPT` — whitelist covers both the package and its submodules |
| B | `paaf_llm/sub/__init__.py` imports `langchain_ollama` | `BROKEN`, reporting `paaf_llm.sub -> langchain_ollama (l.1)` — the carve-out does not leak |

Plan-mandated gates:

- `uv run lint-imports --no-cache` → `Contracts: 3 kept, 0 broken.`
- `uv run pytest tests/negcontrol/test_import_boundary.py --disable-socket -q` → 5 passed
  (1 real-green + 4 red-on-violation, up from 3)
- Full CI equivalent also run: `uv run pytest --disable-socket -q` → 72 passed;
  `uv run pytest tests/test_governance.py tests/negcontrol/test_import_boundary.py` → 39 passed

Targeted check of the new case in isolation confirms it fails for the right reason:

```
langchain-providers-confined-to-adapter BROKEN
paaf_llm_provider_violation is not allowed to import langchain_ollama:
-   paaf_llm_provider_violation -> langchain_ollama (l.18)
```

## Deviations from Plan

**1. [Rule 3 - Blocking] Whitelist expression rewritten from the plan's literal form**

- **Found during:** Task 1
- **Issue:** `paaf_llm._engine.* -> langchain*` is rejected by import-linter 2.13
  (partial-segment wildcard) and, even corrected, would not match `paaf_llm._engine`
  itself.
- **Fix:** Enumerated 14 explicit edges over `paaf_llm._engine` and `paaf_llm._engine.**`;
  added `unmatched_ignore_imports_alerting = warn`.
- **Files modified:** `.importlinter`
- **Commit:** `0515365`

The plan's acceptance criterion — "the whitelist names `paaf_llm._engine.*` as the only
source of every langchain edge, no broader carve-out" — is satisfied in substance:
`paaf_llm._engine` is the only importer named anywhere in the whitelist, and Case B above
demonstrates the carve-out does not extend past it.

Note for downstream: the `.importlinter` header comment and the docstring in
`packages/paaf-llm/src/paaf_llm/_engine/__init__.py` both advertise the old shorthand. The
header comment was corrected in this plan. **The `_engine/__init__.py` docstring was
deliberately left alone** — it is owned by sibling Wave-1 plans and editing it here would
collide at merge. Plan 03-08 should correct that docstring when it writes the adapter.

## Deferred Issues

**`PLW1510` in `tests/negcontrol/test_import_boundary.py` (lines 56, 79)** — `subprocess.run`
without an explicit `check` argument. Verified pre-existing: the same two findings are
present in the file at `HEAD~1` (`git show HEAD:...` before the Task-2 edit), in the
`_run_negcontrol` helper and `test_real_importlinter_is_green`, neither of which this plan
modified. Not CI-blocking either — `.github/workflows/ci.yml` does not invoke ruff at all.
Out of scope per the scope boundary; left untouched.

## Known Stubs

None. Both artifacts are fully wired and exercised by passing tests.

## Threat Flags

None. This plan removes attack surface (closes the provider-import leak, T-03-07) and adds
no new network, auth, file-access, or schema surface.

## Self-Check: PASSED

| Claim | Check | Result |
|-------|-------|--------|
| `.importlinter` modified | file present, contract contains all three provider modules | FOUND |
| `tests/negcontrol/paaf_llm_provider_violation/__init__.py` created | file present | FOUND |
| `tests/negcontrol/.importlinter-negcontrol` extended | `langchain_provider` contract present | FOUND |
| `tests/negcontrol/test_import_boundary.py` extended | `VIOLATION_CASES` has 4 rows | FOUND |
| Commit `0515365` | `git log` | FOUND |
| Commit `b819061` | `git log` | FOUND |
