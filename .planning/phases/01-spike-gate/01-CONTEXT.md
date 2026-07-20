# Phase 1: Spike Gate - Context

**Gathered:** 2026-07-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Throwaway measurement code that replaces the project's five load-bearing unverified claims with evidence. Nothing ships from this phase. Its only durable outputs are recorded measurements — a corpus fixture, generated audio, raw results, and `DECISIONS.md` entries — which constrain every later public claim in the repo.

Covers SPIKE-01 through SPIKE-09. Per roadmap SC#5, no code written here survives into any shipped package.

**This phase decides nothing about architecture.** It produces evidence that later phases decide from.

</domain>

<decisions>
## Implementation Decisions

### Test Corpus (SPIKE-01, 02, 03, 04, 08)

- **D-01:** One shared text corpus of ~20 mixed-script en/ru/he/es sentences serves SPIKE-01, 02, 04 and 08. It is the phase's single measuring instrument.
- **D-02:** Corpus is built as a **deliberate failure grid**, not transcribed real speech. It must systematically cover: single foreign noun in an English frame; mid-clause switch; Hebrew RTL adjacent to Latin digits; proper nouns; numbers/units; and a same-script Russian/English pair.
- **D-03:** The grid must **vary which language is the matrix across sentences**, so all four languages are exercised in both matrix and embedded roles corpus-wide. This is an explicit grid constraint, not an accident of authoring.
- **D-04:** Whisper (SPIKE-04) is fed **Chatterbox TTS output**, not user-recorded speech. User asked whether the model needed fitting — confirmed there is no training or fine-tuning anywhere in this project (PROJECT.md: "we consume open models, we don't make them"); audio is test input only.
- **D-05:** ⚠️ **Binding caveat on D-04.** SPIKE-04 therefore measures *"Whisper on synthetic mixed speech,"* not "Whisper on the user's speech." Under SC#4, no repo text — README included — may claim PAAF handles the user's real code-switched speech on this evidence. Chatterbox failures and Whisper failures are not separable in this setup. This caveat must travel with the SPIKE-04 result into `DECISIONS.md`.
- **D-06:** `language_id` is varied **matrix-plus-embedded**: each sentence rendered twice (once tagged with its dominant language, once with its embedded language), ~40 clips total. Known blind spot: the two untested tags per sentence, partly mitigated by D-03.
- **D-07:** Corpus persists as a **committed text fixture plus the generated WAVs and transcripts**. Declared data, not code — this satisfies SC#5 while letting Phase 7 SC#1 mechanically re-run and diff. Sizing is ~3–5 MB; git-lfs is unnecessary.

### Evidence Handling & Judgment (SPIKE-09)

- **D-08:** **No pre-registered pass/fail thresholds.** Measure first, judge after, with full information. Motivated-reasoning risk was raised and consciously accepted.
- **D-09:** **Raw record is split from interpretation.** Raw output — transcripts, timings, per-clip notes, verbatim reactions — lands in a results file committed before any conclusion is written. `DECISIONS.md` interprets and links back to it. This is what gives D-08 its teeth: evidence stays re-readable without the framing.
- **D-10:** ⚠️ **Phase 1 does NOT select a Hebrew fallback-ladder rung.** It exits with data only. **Obligation created:** Phase 6 planning cannot begin without selecting rung A, B, C, or "none" from Phase 1's data. Phase 6 designs the voice ports including the per-language *engine* override escape hatch, making it the last responsible moment. Without this, Phase 7 SC#2 inherits an unmade decision. (Rung D — per-language voice switching — remains permanently rejected per PROJECT.md.)
- **D-11:** SPIKE-03 measures **Mac MPS and Mac CPU only**. No cloud GPU is rented.
- **D-12:** ⚠️ **Binding caveat on D-11.** The hardware-class recommendation must be recorded as an **inference from Apple Silicon measurements**, explicitly not a measured CUDA result. Required by SC#4, and material because this recommendation directs an actual hardware purchase.

### Hebrew Quality Judgment (SPIKE-02)

- **D-13:** **Verbatim impressions only** — no rating scale, no cloud-TTS baseline comparison. Matches SC#1's literal wording. Known cost: impressions are hard to compare against anything in Phase 7.
- **D-14:** Impressions are captured **per clip, blind to `language_id`**. Clips are shuffled and unlabeled; tags are joined back afterward from a filename mapping. Requires a small shuffle/mapping script. This removes tag expectation from the judgment SPIKE-01 exists to make.

### Framework Bake-Off (SPIKE-05, 06, 07)

- **D-15:** The artifact is **one PAAF-typed port interface, implemented twice** — once over LangChain/LangGraph, once over Pydantic AI. This is what makes "easier to hide behind a port" measurable, and it rehearses the shape Phase 3 builds for real.
- **D-16:** The port covers **model loading from a named profile, streaming tokens, one tool-call round trip, callback-driven tracing, and an MCP server**. Consequently **SPIKE-05 (Ollama token counts non-`None`) and SPIKE-06 (MCP tool args/results visible through callbacks) run *through* the port, not beside it.** Plan this as ONE artifact — do not build the trace/MCP probes separately.
- **D-17:** Comparison evidence is concrete: adapter line count, how many framework types leak toward the boundary, and what each framework fights you on.
- **D-18:** **Findings only carry forward — the port interface does not.** Neither the code nor the interface signatures survive; Phase 3 designs its port fresh, informed by the findings. Strictest reading of SC#5. Accepted cost: Phase 3 redoes design work.
- **D-19:** Stopping rule is **stop at first clear verdict**, even with the second adapter incomplete. **Guard:** the verdict must name what specifically was easier, and record which parts of the unfinished adapter were never built — otherwise the rejected framework is rejected partly on absence of evidence.

### Claude's Discretion

- **D-20:** Listening-pass language coverage — user answered "i don't care." **Call made: Hebrew judged deeply, Russian and Spanish spot-checked.** Rationale: the audio is already rendered so marginal cost is listening time; it matches the lean pattern chosen throughout this discussion; and it closes an SC#4 gap, since the README will claim four languages while SPIKE-02 as written scopes quality judgment to Hebrew alone. A catastrophic Russian or Spanish problem should not stay hidden until Phase 7. Planner may adjust depth, but must not drop ru/es entirely without recording the resulting claim restriction.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition and requirements
- `.planning/ROADMAP.md` §"Phase 1: Spike Gate" — goal, the 5 success criteria, and the "Notes on Structure" paragraph explaining why nothing ships from this phase
- `.planning/REQUIREMENTS.md` §"Phase-0 Validation (SPIKE)" — SPIKE-01 through SPIKE-09 verbatim
- `.planning/PROJECT.md` — Core Value, Constraints, and the Key Decisions table; especially the 2026-07-19 correction paragraph walking back the "STT is a non-issue" claim
- `.planning/STATE.md` — current milestone position and the highest-risk-claim note

### Stack and engine facts (all versions verified 2026-07-13)
- `.claude/CLAUDE.md` §"Technology Stack" — the Hebrew-collapses-the-decision-tree tables, the Phase-0 spike table (numbered 1–7, maps onto SPIKE-01..08), and the Confidence Assessment table marking Chatterbox Hebrew quality and code-switching as LOW confidence
- `.planning/research/STACK.md` — engine and library selection with versions
- `.planning/research/PITFALLS.md` — known failure modes
- `.planning/research/ARCHITECTURE.md` — the five-package structure the port sketch should be PAAF-typed against
- `.planning/research/SUMMARY.md` — research synthesis
- `.planning/research/FEATURES.md` — feature landscape

### Background (compressed into PROJECT.md, retained as reference)
- `project-docs/02-core-software.md` — original core software plan, including the golden-tests-with-a-fake-model approach
- `project-docs/04-landscape-research.md` — competitor landscape
- `project-docs/01-project-management.md` — original project management framing

### External references named in the stack research
- Chatterbox README (`resemble-ai/chatterbox`) — V3 23-language list, `language_id` API, PerTh watermarking
- LangChain release policy (`docs.langchain.com/oss/python/release-policy`) — no breaking changes until 2.0
- Pydantic AI v2 article (`pydantic.dev/articles/pydantic-ai-v2`) — v2 breaking changes, 6mo→3mo stability window

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

None. The repository is greenfield — no Python files, no source packages, no build configuration. Only `.planning/`, `project-docs/`, and agent tooling directories exist.

### Established Patterns

None yet. `.claude/CLAUDE.md` records "Conventions not yet established" and "Architecture not yet mapped."

**Implication for planning:** this phase inherits no patterns and sets none. Phase 2 (Foundation) establishes the uv workspace, import-linter contracts and CI. Phase 1 code must not anticipate that structure — it is throwaway and should stay in a clearly-quarantined location so SC#5 is enforceable by inspection.

### Integration Points

None. Phase 1 connects to no existing system. Its outputs are documents and data fixtures consumed by later phases:
- Corpus fixture + WAVs → re-run by Phase 7 (SC#1: observed behavior must match Phase 1 measurements)
- Fallback-rung data → consumed by Phase 6 planning (see D-10)
- Framework verdict → consumed by Phase 3 (`paaf-llm` adapter choice)
- Latency budget → consumed by Phase 2 (TRACE-04 regression threshold) and Phase 12

</code_context>

<specifics>
## Specific Ideas

- The user reasons about spikes in terms of "what do I actually need to provide" rather than experimental design; questions framed as methodology were less legible than questions framed as concrete artifacts and costs. Downstream agents should present spike work as artifacts and effort, not as protocol.
- Consistent revealed preference across this discussion for the **leaner option** (Mac-only measurement, verbatim-only judgment, data-only exit, no pre-registration) — with one deliberate exception: the framework bake-off, where the user chose the *most* thorough option (callbacks + MCP through the port). Read this as: voice/hardware measurement gets minimum viable effort; the agent-framework decision gets maximum rigor.
- The user explicitly deferred researching real-voice STT evaluation to themselves rather than folding it into this phase.

</specifics>

<deferred>
## Deferred Ideas

- **Record own voice for a real-speech STT evaluation.** User will research this later. Natural home is Phase 7 (Real Engines & Live Audio), whose SC#1 already requires observed behavior to match Phase 1 measurements — real-voice data would strengthen that comparison and lift the D-05 claim restriction. Not added to ROADMAP.md from this workflow; roadmap changes go through `/gsd-phase`.
- **Cloud-GPU / CUDA latency measurement before the hardware purchase.** Declined for Phase 1 (D-11). Remains the obvious way to convert the D-12 inference into a measurement if the purchase decision turns out to be close.
- **Cloud-TTS Hebrew baseline comparison.** Declined as a judgment method (D-13), but it is also direct evidence for fallback rung A. If Phase 6 picks rung A (see D-10), this becomes worth doing then.
- **Pre-registered thresholds for later measurement phases.** Rejected here (D-08). Phase 12 publishes latency and far-field numbers under the same overclaiming pressure; worth reconsidering there.

### Gray areas raised but not discussed

Surfaced during discussion and left for the planner's judgment:
- Where throwaway spike code physically lives so SC#5 is enforceable by inspection
- Spike run order, and whether a catastrophic red-spike result should halt remaining spikes
- How SPIKE-08's per-stage latency budget is structured and reported

</deferred>

---

*Phase: 1-Spike Gate*
*Context gathered: 2026-07-20*
