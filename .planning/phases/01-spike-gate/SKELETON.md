# Walking Skeleton — PAAF Phase 1: Spike Gate

**Phase:** 1
**Generated:** 2026-07-23

## Walking-Skeleton override (read first — this is a deliberate, non-obvious choice)

The mechanical MVP + Walking-Skeleton gate fired for Phase 1 (MVP mode, new project, zero prior
summaries) and the user chose to **keep Walking Skeleton on**. Phase 1 is a **throwaway measurement
phase** with a hard constraint — **SC#5: "No code written in this phase survives into any shipped
package"** (reinforced by **D-18**: neither the bake-off port code nor its interface signatures carry
forward). There is **no database, no UI, no web routing, and no production deployment** in this phase.

Therefore the literal skeleton-template checklist (DB read/write + UI interaction + dev deployment)
is **N/A for a measurement phase**. This decision is recorded here — not buried — so that Phase 7's
verifier (which checks observed behavior against Phase 1 measurements) sees a recorded decision rather
than an unexplained contradiction, and so future phases do not re-litigate Phase 1's minimalism.

**MVP framing reconciliation:** A "vertical slice" in a measurement phase means **each spike track ends
in a recorded MEASUREMENT**, not shipped user-facing functionality. The ROADMAP `**Goal:**` line for
Phase 1 is not in `As a / I want to / so that` form because the actor is the maintainer, not an end
user. The Phase Goal is framed in each PLAN.md as a maintainer-centric user story rather than halting
for `/gsd mvp-phase` — per the orchestrator's explicit Phase-1 reconciliation directive.

## Capability Proven End-to-End

> The smallest end-to-end capability that proves the measuring instruments are wired.

**A single short WAV clip travels Chatterbox-synth → faster-whisper STT → Ollama LLM → Chatterbox TTS
and back out as a WAV, on this machine, with per-stage wall-clock attributed.** That one-clip
WAV-in → WAV-out round trip (**SPIKE-08**, plan `01-09`) is the real walking skeleton: it proves every
stage is wired and co-resident before the full ~40-clip corpus is rendered and judged. The classic
"user sees their name on a dashboard" skeleton is replaced by "the developer sees a wired voice loop
produce measured latency."

## Architectural Decisions

> Phase 1 decides **nothing** about product architecture (CONTEXT.md: "This phase decides nothing about
> architecture"). The decisions below are **measurement-harness** decisions only; none survive per SC#5.

| Decision | Choice | Rationale |
|---|---|---|
| Language / runtime | Python **3.12** via `uv` | Every core dep needs ≥3.10; 3.11 min for `dicta-onnx`; 3.13 has torch/audio wheel risk. Machine has only 3.9.6 → provision. |
| Quarantine location | Everything under top-level `spike/` | SC#5 becomes checkable with one `ls`: Phase 1 ends by deleting `spike/` wholesale. NO root `pyproject.toml`/`pytest.ini` (Phase 2 / FOUND-01 owns the uv workspace). |
| Test config | pytest config **inside `spike/`** | Removed with the directory; must not anticipate the Phase-2 workspace structure (CONTEXT.md §code_context). |
| Surviving data | Corpus + WAVs + transcripts + `01-RESULTS.md` under `.planning/phases/01-spike-gate/`; `DECISIONS.md` at repo root | Declared **data**, not code (D-07). Lets Phase 7 SC#1 mechanically re-run and diff. `spike/` deletion never endangers these fixtures. |
| Venv split | **Two separate venvs**: voice (chatterbox/whisper) and bake-off (langchain/pydantic-ai) | chatterbox hard-pins `torch==2.6.0`/`transformers==5.2.0`/`numpy<2`; resolving that against the LangChain/Pydantic-AI trees is a resolver fight with no upside — the halves never import each other. |
| STT engine for the lock-on question | `faster-whisper==1.2.1` (not mlx-whisper) | Only engine exposing `multilingual=True` per-segment detection + `all_language_probs` — the instrument SPIKE-04 needs. CPU-only on Mac (no Metal backend) but fine for ~40 short clips. |
| Deployment | **None (N/A)** | No shipped artifact; SC#5. The "local full-stack run command" is `uv run pytest spike/` + the round-trip harness. |
| Auth / DB / UI | **None (N/A)** | Measurement phase; see override above. |

## Stack Touched in Phase 1

- [x] Project scaffold — `spike/` quarantine tree, pytest config **inside** `spike/`, shared `conftest.py` fixtures (01-01)
- [ ] ~~Routing~~ — N/A (no web surface)
- [ ] ~~Database read/write~~ — N/A (surviving fixtures are declared files under `.planning/`, not a DB)
- [ ] ~~UI interaction wired to an API~~ — N/A (no UI)
- [x] End-to-end stack proof — one-clip WAV-in → STT → LLM → TTS → WAV-out round trip with per-stage budget (01-09, the skeleton)
- [ ] ~~Deployment to dev environment~~ — N/A; full-stack local run is `uv run pytest spike/ -q` plus the round-trip harness

## Artifacts This Phase Produces

**Throwaway code (deleted with `spike/` at end of phase — SC#5):**
- `spike/README.md`, `spike/pytest.ini` (or `[tool.pytest.ini_options]` inside `spike/`), `spike/conftest.py`
- `spike/voice/gate_readiness.py`, `render_corpus.py`, `measure_ttfa.py`, `transcribe.py`, `shuffle_blind.py`, `roundtrip.py`
- `spike/voice/test_corpus_grid.py`, `test_lang_ids.py`, `test_readiness.py`, `test_blind_mapping.py`, `test_ttfa_harness.py`, `test_transcribe_harness.py`, `test_roundtrip_accounting.py`
- `spike/bakeoff/port.py`, `adapter_langchain.py`, `adapter_pydantic_ai.py`, `mcp_server/` (dependency-light stdio target)
- `spike/bakeoff/test_trace_handler.py`, `test_artifact_capture.py`, `test_port_conformance.py`

**Surviving data (declared fixtures under `.planning/phases/01-spike-gate/`, per D-07):**
- `corpus/corpus.jsonl` — ~20-sentence failure grid (D-01/D-02/D-03)
- `corpus/clips/*.wav` — ~40 rendered clips (matrix + embedded per D-06) plus `language_id=None` control subset
- `corpus/clips_blind/*.wav` + `corpus/mapping.json` — blind-shuffled clips and the reversible tag mapping (D-14)
- `corpus/timings.jsonl`, `corpus/transcripts.jsonl` — raw render timings and STT transcripts + language posteriors
- `raw/voice-provision.md`, `raw/bakeoff-provision.md`, `raw/bakeoff-results.md`, `raw/ttfa.md`, `raw/transcribe.md`, `raw/roundtrip.md`, `raw/hebrew-verdict.md` — per-spike raw notes
- `01-RESULTS.md` — assembled raw record (D-09), committed **before** conclusions

**Surviving conclusions:**
- `DECISIONS.md` (repo root) — measured multilingual reality in plain language (SPIKE-09); carries the D-05 and D-12 caveats; does **not** select a Hebrew fallback rung (D-10)

## Out of Scope (Deferred to Later Slices)

- Selecting the Hebrew fallback-ladder rung (A/B/C/none) — **Phase 6** owns this decision from Phase 1's data (D-10). Rung D (per-language voice switching) is permanently rejected.
- Recording the user's own voice for a real-speech STT eval — deferred by the user to **Phase 7** (D-05 caveat stands until then).
- Cloud-GPU / CUDA latency — declined (D-11); the hardware inference is explicitly Apple-Silicon-only (D-12).
- Any uv workspace, import-linter contract, or CI gate — **Phase 2 / FOUND-01** owns these; Phase 1 must not anticipate them.

## Subsequent Slice Plan

Each later phase builds on this phase's **evidence** (not its code):

- **Phase 2 (Foundation):** consumes the SPIKE-08 latency budget as the TRACE-04 regression threshold; establishes the real uv workspace.
- **Phase 3 (paaf-llm Core):** consumes the SPIKE-05/06/07 framework verdict to choose the adapter; designs its port **fresh** (D-18).
- **Phase 6 (paaf-voice Ports & Fakes):** consumes the Hebrew fallback-rung data (D-10) and the aggregator evidence.
- **Phase 7 (Real Engines):** re-runs and diffs against `corpus/` fixtures (SC#1: observed behavior must match Phase 1 measurements); documents Chatterbox watermarking (VOICE-12).
- **Phase 12 (Launch):** OSS-06 — public multilingual claims must match SPIKE-01..04 measurements exactly.
