---
phase: 01-spike-gate
plan: 01
subsystem: infra
tags: [uv, python-3.12, ffmpeg, pytest, pytest-asyncio, homebrew, scaffolding]

# Dependency graph
requires: []
provides:
  - "Provisioned toolchain: uv 0.11.31, CPython 3.12.13, ffmpeg 8.1.2 (all on PATH)"
  - "spike/ quarantine tree (voice/ + bakeoff/) — SC#5 enforceable by one `ls`"
  - "spike/pytest.ini — pytest config INSIDE spike/, `slow` marker, --strict-markers, asyncio_mode=auto"
  - "spike/conftest.py — framework-free shared fixtures: tmp_corpus, fake_model, fake_tool, device"
  - "spike/.venv — base test env (pytest 9.1.1 + pytest-asyncio 1.4.0), git-ignored"
  - "Root .gitignore protecting spike venvs and model weights while leaving corpus WAVs committable"
affects: [01-02, 01-03, 01-04, 01-05, 01-06, 01-07, 01-08, 01-09, 01-10]

# Tech tracking
tech-stack:
  added: [uv 0.11.31, CPython 3.12.13, ffmpeg 8.1.2, pytest 9.1.1, pytest-asyncio 1.4.0]
  patterns:
    - "Quarantine directory: all throwaway phase code under one top-level dir whose deletion is the SC#5 check"
    - "Test config lives inside the quarantine, never at repo root (Phase 2 / FOUND-01 owns the workspace)"
    - "Shared fixtures import stdlib + pytest only, so they collect in both the voice and bake-off venvs"

key-files:
  created:
    - spike/README.md
    - spike/pytest.ini
    - spike/conftest.py
    - spike/test_fixtures_smoke.py
    - .gitignore
  modified: []

key-decisions:
  - "spike/pytest.ini uses `testpaths = .` — pytest's rootdir IS spike/ because this is the nearest ini file to the `spike/` argument, so `.` resolves to spike/"
  - "`slow` is NOT filtered via addopts; the quick suite passes `-m \"not slow\"` explicitly so the full suite needs no undoing of a default"
  - "The base test venv lives at spike/.venv, not repo root — a root .venv would leave a Phase-1 artifact outside spike/ and weaken the one-`ls` SC#5 check"
  - "The canonical invocation is `uv run --python spike/.venv/bin/python pytest spike/ -q`; a bare `uv run pytest` cannot resolve without a root project or root venv"
  - "ffmpeg was installed as the plan directs even though 01-RESEARCH judged it unnecessary — it is cheap insurance against a silent audio decode-path failure in SPIKE-04/08"
  - "SPIKE-09 was NOT marked complete: plan 01-10 owns the actual DECISIONS.md deliverable and this plan only builds its scaffold"

patterns-established:
  - "Quarantine pattern: `spike/` holds all disposable code; surviving data lives under .planning/phases/01-spike-gate/ (D-07)"
  - "Framework-free doubles pattern: FakeModel/FakeTool are plain objects, so the fast suite runs in any venv"
  - "Device-as-string pattern: the `device` fixture yields \"cpu\"/\"mps\" strings, never torch.device (Chatterbox compares by string)"

requirements-completed: []

coverage:
  - id: D1
    description: "System toolchain provisioned: uv, CPython 3.12, and ffmpeg all resolvable on PATH"
    requirement: "SPIKE-09"
    verification:
      - kind: integration
        ref: "uv --version && uv python find 3.12 && ffmpeg -version | head -1"
        status: pass
    human_judgment: false
  - id: D2
    description: "spike/ quarantine tree exists with voice/ and bakeoff/, a disposability README citing SC#5 and D-18, and no root pyproject.toml or pytest.ini"
    requirement: "SPIKE-09"
    verification:
      - kind: integration
        ref: "test -f spike/README.md && test -f spike/pytest.ini && test -f spike/conftest.py && grep -qi 'slow' spike/pytest.ini && ! test -f pytest.ini && ! test -f pyproject.toml"
        status: pass
    human_judgment: false
  - id: D3
    description: "Shared pytest fixtures (tmp_corpus, fake_model, fake_tool, device[cpu|mps]) collect and behave correctly under a pytest run rooted at spike/"
    requirement: "SPIKE-09"
    verification:
      - kind: unit
        ref: "spike/test_fixtures_smoke.py (10 tests) via `uv run --python spike/.venv/bin/python pytest spike/ -q`"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-07-23
status: complete
---

# Phase 1 Plan 01: Spike Scaffold Summary

**Provisioned uv 0.11.31 + CPython 3.12.13 + ffmpeg 8.1.2, and stood up the `spike/` quarantine tree with pytest configured inside it — `slow` marker, framework-free shared fixtures, and a 10-test smoke suite that passes in 0.01s.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-23T10:07:00Z (approx.)
- **Completed:** 2026-07-23T10:19:00Z
- **Tasks:** 2
- **Files created:** 7 (5 tracked source/doc files + 2 `.gitkeep` placeholders)

## Provisioning Baseline

These versions are the record for `01-RESULTS.md`. Machine: Apple M3 Pro, 18 GB unified memory, macOS 26.5.2, arm64.

| Tool | Resolved version | Path / source |
|---|---|---|
| `uv` | **0.11.31** (Homebrew 2026-07-22, aarch64-apple-darwin) | `/opt/homebrew/bin/uv` |
| CPython | **3.12.13** (macos-aarch64-none) | `~/.local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12` |
| `ffmpeg` | **8.1.2** (Homebrew bottle, 2026) | `/opt/homebrew/bin/ffmpeg` |
| `pytest` | **9.1.1** | `spike/.venv` |
| `pytest-asyncio` | **1.4.0** | `spike/.venv` |
| Homebrew | 6.0.1 | pre-existing |
| Node.js | v24.16.0 | pre-existing (stdio MCP target, SPIKE-06) |

Still unprovisioned and **owned by a later plan**: the Ollama daemon (SPIKE-05/06/07/08), the voice venv (01-03), the bake-off venv (01-04). `HF_TOKEN` was deliberately **not** set — all models are public (RESEARCH §Security Domain V6).

## Accomplishments

- **Toolchain unblocked.** The machine had only system Python 3.9.6, which fails `chatterbox-tts` (`>=3.10`), `dicta-onnx` (`>=3.11`) and `langchain` (`>=3.10`). 3.12.13 is now installed and resolvable; 3.13 was avoided per the CLAUDE.md pin (torch/audio wheel risk).
- **SC#5 is now a one-`ls` property.** Everything disposable lives under `spike/`; `spike/README.md` states that plainly, cites SC#5 and D-18, and tabulates exactly what dies with the directory versus what survives under `.planning/phases/01-spike-gate/` (D-07).
- **No root workspace was created.** No `pyproject.toml`, no `pytest.ini`, no `.python-version`, no `.venv` at repo root — Phase 2 (FOUND-01) owns that, and Phase 1 must not anticipate it. Verified by explicit `! test -f` assertions.
- **The runner is real, not vacuous.** `spike/test_fixtures_smoke.py` (10 tests, 0.01s) exercises every shared fixture, including a non-ASCII round-trip guard so a mojibake corpus can never silently invalidate a language measurement downstream.
- **`--strict-markers` is on**, so a typo'd `@pytest.mark.slwo` in a later plan is an error rather than a silently-unfiltered model download.

## Task Commits

1. **Task 1: Install the missing system toolchain (uv, Python 3.12, ffmpeg)** — no commit (pure system provisioning; no repository files changed, per the plan's own `<files>` note). Outcomes recorded in the Provisioning Baseline table above.
2. **Task 2: Create the spike/ quarantine tree with pytest configured inside it** — `13fd6ec` (chore)

**Plan metadata:** see the `docs(01-01)` commit following this SUMMARY.

## Files Created/Modified

- `spike/README.md` — declares the tree throwaway, cites SC#5 and D-18, tabulates the survives-vs-deleted split (D-07), records the exact quick/full test commands and the two-venv split rationale.
- `spike/pytest.ini` — `[pytest]` config kept *inside* `spike/` so it dies with the directory. Registers the `slow` marker (model-touching tests), sets `testpaths = .`, `asyncio_mode = auto`, and `addopts = --strict-markers`. Carries an inline warning against moving it to repo root.
- `spike/conftest.py` — shared fixtures, importing **stdlib + pytest only**:
  - `tmp_corpus` — writes a 3-record throwaway `corpus.jsonl` to `tmp_path` using the exact five-key schema (`id`, `text`, `matrix_lang`, `embedded_lang`, `category`) that 01-02 authors for real, so harnesses can be exercised without the real grid.
  - `fake_model` / `FakeModel` — records every call, replays scripted replies, exposes sync + async invoke and stream, reports a usage dict, and can be told to raise.
  - `fake_tool` / `FakeTool` — returns the two-part `(content, artifact)` shape on purpose; a double returning a bare string could not falsify SPIKE-06's artifact-survival question.
  - `device` — parametrized over the **strings** `"cpu"` and `"mps"`, with the reason documented inline (Chatterbox's `from_pretrained` does `device == "mps"` string equality despite its `torch.device` hint) plus the D-11 note that an MPS failure is a valid recorded measurement, not a blocker.
- `spike/test_fixtures_smoke.py` — 10 tests proving the above.
- `spike/voice/.gitkeep`, `spike/bakeoff/.gitkeep` — git cannot track empty directories; these hold the tree shape until 01-02..01-09 fill it.
- `.gitignore` (new, repo root) — ignores `spike/**/.venv/`, `__pycache__/`, `.pytest_cache/`, and model-weight extensions (`*.safetensors`, `*.ckpt`, `*.pt`, `*.onnx`, `*.gguf`). Carries an explicit comment that a blanket `*.wav` rule must **not** be added, because the rendered corpus clips under `.planning/phases/01-spike-gate/corpus/clips/` are committed on purpose (D-07, ~3–5 MB, no git-lfs).

## Decisions Made

- **`testpaths = .` rather than `spike`.** Because `spike/pytest.ini` is the nearest ini file to the `spike/` argument, pytest sets `rootdir=/…/paaf/spike`, and `testpaths` is resolved relative to rootdir. `testpaths = spike` would have pointed at `spike/spike`. Verified: `configfile: pytest.ini`, `rootdir: …/paaf/spike`.
- **`slow` is not filtered by default.** VALIDATION.md lists the quick suite as excluding `slow` and the full suite as including it, but the two commands as literally written are identical. Putting `-m "not slow"` in `addopts` would have made the *full* suite unable to run `slow` tests without undoing a default. Resolution: keep `addopts` marker-free and pass `-m "not slow"` explicitly on the quick run. Both forms are recorded in `spike/README.md`.
- **Base venv at `spike/.venv`, not repo root.** A root `.venv` would make `uv run pytest spike/ -q` work verbatim, but at the cost of leaving a Phase-1 artifact outside `spike/` — directly weakening the SC#5 one-`ls` property this plan exists to establish. The venv went inside the quarantine instead; see the deviation below for the resulting command change.
- **`asyncio_mode = auto`.** Later harnesses (bake-off streaming, MCP stdio) are async. If a downstream venv omits `pytest-asyncio`, pytest emits an "Unknown config option" warning rather than failing — which is itself the signal that the venv is under-provisioned.
- **`SPIKE-09` deliberately left unchecked in REQUIREMENTS.md.** See deviations.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `uv run pytest spike/ -q` cannot resolve an interpreter without a root project**

- **Found during:** Task 2 (verification)
- **Issue:** The plan's and VALIDATION.md's verification command is `uv run pytest spike/ -q` run from the repository root. With no root `pyproject.toml` and no root `.venv` — both of which Phase 1 is forbidden to create — `uv run` has nothing to resolve against and fails with `error: Failed to spawn: 'pytest' … No such file or directory`. Creating a root `.venv` to make the literal command work would have undermined the SC#5 one-`ls` property that is this plan's entire point.
- **Fix:** Created the base test env inside the quarantine at `spike/.venv` and adopted `uv run --python spike/.venv/bin/python pytest spike/ -q` as the canonical invocation. Recorded in `spike/README.md` alongside the per-half venv paths that 01-03/01-04 will create.
- **Files modified:** `spike/README.md`
- **Verification:** `uv run --python spike/.venv/bin/python pytest spike/ -q` → `10 passed in 0.01s`, exit 0.
- **Committed in:** `13fd6ec`

**2. [Rule 2 - Missing Critical] Added a fixture smoke test so the runner cannot pass vacuously**

- **Found during:** Task 2
- **Issue:** The plan's acceptance criteria permit `uv run pytest spike/ -q` to collect *zero* tests. A green-on-empty runner proves nothing: a `conftest.py` with a broken fixture, a bad encoding, or a mis-scoped parametrization would still report success, and the breakage would first surface inside a measurement harness in a later plan — exactly where it is most expensive to diagnose.
- **Fix:** Added `spike/test_fixtures_smoke.py` — 10 tests covering the corpus schema and its non-ASCII (Hebrew/Cyrillic) round-trip, `FakeModel` call recording / scripted replay / streaming / usage / induced failure, `FakeTool`'s `(content, artifact)` pair, and the `device` fixture's string-ness. It lives inside `spike/`, so it dies with the directory.
- **Files modified:** `spike/test_fixtures_smoke.py`
- **Verification:** 10 passed; `pytest --markers` confirms `slow` is registered; `--collect-only` confirms `device` parametrizes to `[cpu]` and `[mps]`.
- **Committed in:** `13fd6ec`

**3. [Rule 2 - Missing Critical] Added a root `.gitignore` (explicitly requested at dispatch)**

- **Found during:** Task 2
- **Issue:** The repository had **no `.gitignore` at all**. Plans 01-03 and 01-04 create multi-GB venvs under `spike/`, and Chatterbox (~3.2 GB) plus Whisper (~3 GB) weights land wherever the harness points its cache. Without an ignore file the first `git add` in a later plan could commit gigabytes.
- **Fix:** Created `.gitignore` covering venvs, Python caches, and model-weight extensions — with an explicit inline comment forbidding a blanket `*.wav` rule, since the surviving corpus clips (D-07) must remain committable.
- **Files modified:** `.gitignore`
- **Verification:** `git check-ignore -v spike/.venv/bin/python` → matched by `.gitignore:11:spike/**/.venv/`; `git status --untracked-files=all -- spike/` lists only the six intended files.
- **Committed in:** `13fd6ec`

**4. [Rule 3 - Blocking] Added `.gitkeep` placeholders to `spike/voice/` and `spike/bakeoff/`**

- **Found during:** Task 2
- **Issue:** The plan directs creating both directories, but git cannot track empty directories — they would have vanished from the commit, and a fresh clone would not show the tree shape the plan describes.
- **Fix:** Added empty `.gitkeep` files. They are removed naturally when 01-02..01-09 populate the directories, and in any case die with `spike/`.
- **Files modified:** `spike/voice/.gitkeep`, `spike/bakeoff/.gitkeep`
- **Verification:** `git status --untracked-files=all -- spike/` shows both tracked.
- **Committed in:** `13fd6ec`

### Deliberate non-action

**5. `SPIKE-09` was NOT marked complete in REQUIREMENTS.md**

The plan's frontmatter lists `requirements: [SPIKE-09]`, but SPIKE-09 reads *"Record the measured multilingual reality in `DECISIONS.md`, and constrain every public claim to what was measured."* Plan `01-10` carries the same requirement ID and owns that deliverable; no measurement has been taken and `DECISIONS.md` does not exist. Checking the box now would put a false claim into the traceability matrix that the SC#4 claim audit is specifically meant to catch. `requirements-completed: []` in this SUMMARY's frontmatter reflects that. `01-10` should mark SPIKE-09 complete.

### Conflict resolved in favour of the plan

**6. ffmpeg: RESEARCH says "not needed", the plan says install it**

`01-RESEARCH.md` §Environment Availability marks ffmpeg **"Not needed — faster-whisper 1.2.1 uses PyAV; `soundfile` covers WAV I/O."** The plan's Task 1 nonetheless directs installing it, reasoning that its absence would produce a silent decode-path failure that would sink SPIKE-04/08. Installed as the plan directs — it is a ~53 MB bottle and cheap insurance. Noted here so the discrepancy is visible rather than buried.

---

**Total deviations:** 4 auto-fixed (2 blocking, 2 missing-critical), 1 deliberate non-action, 1 documented conflict.
**Impact on plan:** No scope creep. Two deviations were forced by facts on the ground (uv's resolution model; git's inability to track empty dirs); two closed real correctness gaps (a vacuously-green runner, an absent `.gitignore` in front of multi-GB downloads). Every plan acceptance criterion still passes verbatim.

## Issues Encountered

- **`brew install ffmpeg` pulled a large dependency chain** (sdl3, sdl2-compat, svt-av1, x264, x265, …). Completed without error; total ffmpeg cellar 53.1 MB.
- **`uv python find 3.12` resolves to uv's own managed CPython**, not a Homebrew python. That is intended — it keeps the interpreter under uv's control for the per-half venvs in 01-03/01-04.

## Known Stubs

None. Every artifact this plan produces is complete for its purpose; the empty `spike/voice/` and `spike/bakeoff/` directories are placeholders **by design** and are filled by plans 01-02 through 01-09.

## Deferred — Human Action Required

None for this plan. Nothing here requires listening, judging, purchasing, or authenticating.

For situational awareness, the human-gated items still ahead in this phase are the native-ear Hebrew verdict (SPIKE-02 / D-13, blind per D-14), the Russian/Spanish spot-checks (D-20), and the SC#4 claim audit (SPIKE-09) — all owned by later plans.

## User Setup Required

None — no external service configuration. `HF_TOKEN` is deliberately unset; all models used by this phase are public.

## Next Phase Readiness

**Ready.** Wave 2 can start immediately:

- **01-02** (corpus authoring) can write `spike/voice/test_corpus_grid.py` and run it red — the runner, the `slow` marker and the `tmp_corpus` schema reference are all in place.
- **01-03 / 01-04** should create `spike/.venv-voice` and `spike/.venv-bakeoff` next to the existing `spike/.venv`; the `.gitignore` already covers them, and `spike/conftest.py` imports nothing that would break collection in either.

**Carried concerns:**

- **Ollama is still not installed** and gates SPIKE-05/06/07/08 (four of nine requirements). Whichever plan claims it must also pick the model on **tool-calling reliability**, re-checked at implementation time per CLAUDE.md §Decision 6 — not taken on the roadmap's word.
- The `device` fixture parametrizes over `"mps"` unconditionally. MPS on Chatterbox is documented-unreliable; per D-11 a failure there is **data**, and downstream plans must record the failure rather than skip it away silently.

## Self-Check: PASSED

Files verified present on disk:

- `spike/README.md` — FOUND
- `spike/pytest.ini` — FOUND
- `spike/conftest.py` — FOUND
- `spike/test_fixtures_smoke.py` — FOUND
- `spike/voice/.gitkeep` — FOUND
- `spike/bakeoff/.gitkeep` — FOUND
- `.gitignore` — FOUND

Absent as required:

- root `pyproject.toml` — ABSENT (correct)
- root `pytest.ini` — ABSENT (correct)
- root `.python-version` — ABSENT (correct)

Commit verified: `13fd6ec` present in `git log`, 7 files changed, 395 insertions, **0 deletions**.

Plan verification commands re-run at self-check time, all green:

- `uv --version && uv python find 3.12 && ffmpeg -version | head -1` → exit 0
- `test -f spike/README.md && … && ! test -f pytest.ini && ! test -f pyproject.toml` → exit 0
- `uv run --python spike/.venv/bin/python pytest spike/ -q` → `10 passed in 0.01s`, exit 0

---
*Phase: 01-spike-gate*
*Completed: 2026-07-23*
