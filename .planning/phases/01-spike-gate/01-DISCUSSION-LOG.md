# Phase 1: Spike Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-20
**Phase:** 1-Spike Gate
**Areas discussed:** The sentence corpus, Pre-registered pass rules, Hebrew verdict method, Bake-off shape

---

## The Sentence Corpus

### Q1 — Where does Whisper's audio come from? (SPIKE-04)

| Option | Description | Selected |
|--------|-------------|----------|
| You record yourself | ~20 sentences spoken into a mic; real prosody, real code-switch timing, the actual voice the product must handle | |
| Chatterbox TTS output | Synthesize with Chatterbox, feed to Whisper; zero recording effort but circular — cannot separate which engine failed | ✓ |
| Both, labeled separately | Recordings as primary, TTS round-trip as a second labeled data point that also serves SPIKE-08 | |

**User's choice:** Chatterbox TTS output.
**Notes:** User first asked a clarifying question — *"why should we provide something to whisper? we need to fit this model here? it can't do it out of the box?"* — indicating a concern that the spike involved training or fine-tuning. Clarified that no training occurs anywhere in the project (PROJECT.md: "we consume open models, we don't make them"), that audio is test input rather than training data, and that PROJECT.md's own 2026-07-19 correction is what makes the out-of-the-box behavior an open question (Whisper emits one language token per 30-second window and tends to lock onto a single language). User then selected the synthetic path and added: *"I will research it later (add a research point for me in the roadmap)."* Recorded as a deferred idea; ROADMAP.md was not edited from this workflow.

### Q2 — What should the ~20 sentences contain?

| Option | Description | Selected |
|--------|-------------|----------|
| Things you really say | ~20 genuine recent utterances; highest validity, requires honest recall | |
| Deliberate failure grid | Systematic coverage of noun insertion, mid-clause switch, RTL beside Latin digits, proper nouns, numbers/units, same-script ru/en pair | ✓ |
| Mostly real, some adversarial | ~14 genuine plus ~6 constructed edge cases, tagged separately | |

**User's choice:** Deliberate failure grid.
**Notes:** Noted that the grid also supplies vocabulary for describing failures precisely in `DECISIONS.md`.

### Q3 — What form does the corpus take?

| Option | Description | Selected |
|--------|-------------|----------|
| Committed data fixture | Structured YAML/JSON, declared data-not-code so SC#5 holds | |
| Table in DECISIONS.md | Single source of truth, but Phase 7 must re-key by hand | |
| Fixture plus generated WAVs | Text fixture, audio files and transcripts all committed; strongest provenance | ✓ |

**User's choice:** Fixture plus generated WAVs.
**Notes:** Raised as a lifetime tension — SC#5 says no code survives, but Phase 7 SC#1 requires re-running the same corpus. Repo-weight concern was resolved: ~20 short sentences is roughly 3–5 MB, below the threshold where git-lfs is worth the complexity.

### Q4 — How is `language_id` varied?

| Option | Description | Selected |
|--------|-------------|----------|
| Full sweep, all four | 4 renders per sentence (~80 clips); directly answers whether any single fixed tag can carry mixed speech | |
| Matrix language only | 1 render per sentence (~20 clips); fastest, but a failure cannot be attributed to the tag choice | |
| Matrix plus embedded | 2 renders per sentence (~40 clips); shows tag sensitivity at half the cost of a sweep | ✓ |

**User's choice:** Matrix plus embedded.
**Notes:** Framed against the founding "no language configuration anywhere" rule (VOICE-01) — at runtime the system must pass a `language_id` it never asked the user for, so the spike must reveal what that value can be. Blind spot of two untested tags per sentence was noted, along with the mitigation of varying the matrix language across the grid.

---

## Pre-registered Pass Rules

### Q1 — Do we pre-commit pass/fail rules and consequences?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-register everything | Thresholds and consequences written to DECISIONS.md before any spike runs | |
| Pre-register the red ones | Pre-commit only the three 🔴 spikes driving the language promise and hardware purchase | |
| Measure first, judge after | Record raw results honestly, then interpret with full information | ✓ |

**User's choice:** Measure first, judge after.
**Notes:** Bias risk was raised explicitly — user is both experimenter and the person invested in the project succeeding, and the two highest-risk measurements have the most room for motivated interpretation. User accepted that risk. Counter-argument acknowledged in return: thresholds set before hearing a single sample can be wrong in both directions.

### Q2 — How do we keep raw measurements separable from interpretation?

| Option | Description | Selected |
|--------|-------------|----------|
| Split record and verdict | Raw results file committed before any conclusion is written; DECISIONS.md interprets and links back | ✓ |
| One DECISIONS.md narrative | Everything in one write-up; simplest, but results and framing become inseparable | |
| Split, and commit raw first | Same split, with raw evidence in its own earlier commit for timestamp provenance | |

**User's choice:** Split record and verdict.
**Notes:** Offered as the narrow fix that gives "measure first" its teeth without pre-registering anything — the residual risk was never the timing of the judgment but whether raw evidence survives independently of the interpretation.

### Q3 — Must Phase 1 exit with a fallback-ladder rung selected?

| Option | Description | Selected |
|--------|-------------|----------|
| Pick the rung at exit | DECISIONS.md names A/B/C/none with justifying measurement; Phases 6–7 build against a known target | |
| Data only, decide later | Rung chosen at Phase 6 planning when voice architecture is concrete | ✓ |
| Rung plus a revisit trigger | Name a rung now, plus the condition that would reopen it | |

**User's choice:** Data only, decide later.
**Notes:** Argued that a gate deciding nothing is a checkpoint. User held. Consequence converted into an explicit obligation in CONTEXT.md (D-10): Phase 6 planning cannot begin without selecting a rung, since Phase 6 designs the ports including the per-language engine override and is therefore the last responsible moment. Rung D remains permanently rejected.

### Q4 — Real GPU data point, or Mac numbers alone?

| Option | Description | Selected |
|--------|-------------|----------|
| Rent a cloud GPU once | A few dollars for one real CUDA time-to-first-audio number on the decision that spends the hardware budget | |
| Mac numbers only | MPS and CPU exactly as the roadmap specifies; hardware advice becomes an inference | ✓ |
| Mac now, GPU before buying | CUDA measurement attached to the purchase decision rather than this phase | |

**User's choice:** Mac numbers only.
**Notes:** Gap raised: roadmap SC#2 asks Phase 1 to say what class of hardware to buy, but Apple Silicon → Linux CUDA is an extrapolation. Since SC#4 forbids claims exceeding measurement, the labeling requirement was recorded as binding (D-12) rather than advisory.

---

## Hebrew Verdict Method

### Q1 — How is Chatterbox's Hebrew judged?

| Option | Description | Selected |
|--------|-------------|----------|
| Against a cloud baseline | Rate relative to Azure/Google Hebrew; fixes a reference point and doubles as evidence for fallback rung A | |
| Verbatim impressions only | Unstructured written reactions, per SC#1's literal wording | ✓ |
| Scored on fixed dimensions | Intelligibility, nativeness, prosody, damage to non-Hebrew parts, plus verbatim reaction | |

**User's choice:** Verbatim impressions only.
**Notes:** Matches SC#1 literally. Known cost acknowledged: unstructured impressions are hard to compare against anything in Phase 7.

### Q2 — How are impressions captured while listening?

| Option | Description | Selected |
|--------|-------------|----------|
| Per clip, blind to tag | Shuffled unlabeled clips; `language_id` joined back afterward from a filename mapping | ✓ |
| Per clip, tag visible | Simpler, allows noticing tag patterns live, but expectation precedes hearing | |
| One summary after listening | Closest to natural description; loses per-clip detail Phase 7 would diff against | |

**User's choice:** Per clip, blind to tag.
**Notes:** Offered as a cheap sharpening compatible with verbatim-only — since SPIKE-01's entire question is tag sensitivity, knowing the tag while listening lets expectation do part of the hearing. Costs one shuffle/mapping script.

### Q3 — Does the listening pass cover Russian and Spanish?

| Option | Description | Selected |
|--------|-------------|----------|
| All four, Hebrew deepest | Same blind pass across en/ru/he/es; audio already exists so marginal cost is listening time | |
| Hebrew only, as scoped | Strictly SPIKE-02; no repo text may then characterize ru/es output quality | |
| Hebrew deep, others spot-check | Full pass on Hebrew, sampling on ru/es to catch a catastrophic problem | ✓ (Claude's call) |

**User's choice:** *"i dont care"* — deferred to Claude.
**Notes:** Gap surfaced by Claude rather than the roadmap: SPIKE-02 scopes quality judgment to Hebrew, but the README will claim four languages and SC#4 forbids unsupported claims. Claude selected the spot-check middle option; rationale recorded in CONTEXT.md D-20.

---

## Bake-off Shape

### Q1 — What artifact makes "easier to hide behind a port" measurable?

| Option | Description | Selected |
|--------|-------------|----------|
| One port, two adapters | Single PAAF-typed port implemented over both frameworks; compare adapter size, type leakage, friction | ✓ |
| Checklist against docs | Score both from documentation without writing adapters | |
| Adapters plus a trace drain | Both adapters plus SQLite drain, folding SPIKE-05 and SPIKE-06 into the same artifact | |

**User's choice:** One port, two adapters.
**Notes:** The checklist option was flagged as contradicting PROJECT.md, which states this question cannot be settled by reading.

### Q2 — What surface does the port cover?

| Option | Description | Selected |
|--------|-------------|----------|
| Load, stream, tool-call | Wide enough that framework types actually try to leak, few hundred lines | |
| Load and stream only | Smallest build, but both frameworks look clean at this surface — risks a verdict that says nothing | |
| Add callbacks and MCP | Plus callback tracing and an MCP server, so SPIKE-05 and SPIKE-06 run through the port | ✓ |

**User's choice:** Add callbacks and MCP.
**Notes:** This answer converges with the "adapters plus a trace drain" option declined in Q1. Reconciled explicitly: SPIKE-05 and SPIKE-06 now run through the port as ONE artifact, and the plan must not build separate trace/MCP probes. Notable as the single place in this discussion where the user chose the most thorough option rather than the leanest.

### Q3 — What carries forward from the port sketch?

| Option | Description | Selected |
|--------|-------------|----------|
| Interface as a document | Signatures and PAAF types recorded as a design output; Phase 3 reimplements from spec | |
| Findings only, no interface | Only the verdict and leakage notes; Phase 3 designs fresh | ✓ |
| Document it, mark provisional | Interface written down but explicitly non-binding on Phase 3 | |

**User's choice:** Findings only, no interface.
**Notes:** Strictest reading of SC#5. Accepted cost: Phase 3 redoes design work already performed. Benefit: Phase 3 is not anchored to a throwaway sketch.

### Q4 — What stops the bake-off from expanding?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed timebox per adapter | Hard cap; unfinished work becomes a finding, converting overrun into data | |
| Stop at first clear verdict | Halt once one framework is obviously easier, even if the second adapter is incomplete | ✓ |
| Feature-complete both | Fairest comparison, open-ended against a 20 h/week budget on deleted code | |

**User's choice:** Stop at first clear verdict.
**Notes:** Risk noted — the incomplete adapter is the one being rejected. Guard added (D-19): the verdict must name what specifically was easier and record which parts of the unfinished adapter were never built.

---

## Claude's Discretion

- **Listening-pass language coverage.** User answered "i dont care." Claude selected Hebrew-deep with Russian and Spanish spot-checks. See CONTEXT.md D-20.

## Deferred Ideas

- Record own voice for a real-speech STT evaluation — user to research; natural home is Phase 7.
- Cloud-GPU / CUDA latency measurement before the hardware purchase.
- Cloud-TTS Hebrew baseline comparison — becomes relevant if Phase 6 selects fallback rung A.
- Pre-registered thresholds for later measurement phases — worth reconsidering at Phase 12.
- Three gray areas surfaced but not discussed, left to planner judgment: where throwaway spike code lives, spike run order and red-spike halt conditions, and SPIKE-08 latency-budget structure.
