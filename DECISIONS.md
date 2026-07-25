# DECISIONS.md

The interpretation of Phase 1's measured evidence — what each spike answered, what stands, what
changed, and what is still pending. Per D-09 this file is written **after** and links **back to**
the raw record, which stays re-readable without this framing:

- **Raw evidence:** [`.planning/phases/01-spike-gate/01-RESULTS.md`](.planning/phases/01-spike-gate/01-RESULTS.md) (committed first, D-09).
- Underlying durable records: `.planning/phases/01-spike-gate/raw/*.md` and `.planning/phases/01-spike-gate/corpus/*.jsonl`.

**Two caveats are binding on every claim derived here and travel with their results wherever cited:**

> **D-05 — synthetic-speech caveat (SPIKE-04 / STT):** every STT finding measures Whisper on
> **synthetic Chatterbox speech**, not the user's real code-switched voice (D-04). Chatterbox and
> Whisper failures are **not separable**. No claim anywhere in the repo may say PAAF handles the
> user's real code-switched speech on this evidence (SC#4). Real-voice evaluation is deferred to
> Phase 7.

> **D-12 — Apple-Silicon caveat (SPIKE-03 / SPIKE-08 / latency):** every latency number is an
> Apple-Silicon (M3 Pro, 18 GB) measurement. The hardware-class recommendation is an **inference
> from Apple Silicon, explicitly NOT a measured CUDA result** (D-11/D-12). It directs a real
> purchase, so the caveat is not decoration.

---

## The measured multilingual reality, in plain language (SPIKE-09)

This is the durable statement the rest of the repo may not exceed (SC#4).

### Does Chatterbox produce intelligible Hebrew? — **NOT YET KNOWN. Pending a human native-ear verdict.**

Plan 01-08 — the blind native-ear Hebrew judgment (D-13/D-14) and the D-20 Russian/Spanish
spot-check — **was not executed.** There is no `raw/hebrew-verdict.md`. The 46 blind clips are
rendered and on disk, but **no one has listened to them**, and per D-13 no quality property may be
inferred from render statistics, Whisper transcripts, or any other proxy. See
[01-RESULTS.md §2](.planning/phases/01-spike-gate/01-RESULTS.md). **Status: PENDING — awaiting
human native-ear verdict (plan 01-08).** Until it exists, the repo makes **no** claim about
Chatterbox Hebrew quality, and **no Hebrew fallback-ladder rung may be selected** (see below, D-10).

### Did intra-sentence code-switching work? — **Partially measured; the intelligibility half is pending.**

What is measured ([01-RESULTS.md §1, §3](.planning/phases/01-spike-gate/01-RESULTS.md)):
- Chatterbox rendered all 20 mixed-script sentences under both matrix and embedded `language_id` tags (46 clips), and the tag demonstrably drives the dominant acoustic language (it flipped Whisper's detected language on 9/20 sentences).
- Whether the *audio* is an intelligible code-switch is a **listening** judgment that depends on the pending 01-08 verdict. This report does not claim code-switching "works"; it records that the render exists and the tag has acoustic effect.

### What does Whisper do with mixed script? — **It locks to ONE language and does not switch.** (with D-05)

Measured with the right instrument ([01-RESULTS.md §3](.planning/phases/01-spike-gate/01-RESULTS.md)):
- **Whisper large-v3 assigns exactly one language per clip.** The `multilingual=True` "detect on every segment" flag changed **nothing** — the posterior was byte-identical to `multilingual=False` on 46/46 clips.
- The **other** language is **transliterated or garbled into Latin** when the matrix language is Latin (`סופגניות`→"Sifakonat", `sobremesa`→"Sober Misa"); it is **preserved in native script only when Whisper locked to the non-Latin language** (a Russian-locked clip keeps Cyrillic + English).
- The **same-script Russian/English** pair collapses entirely (`СОК`→"Sock").
- **`task=translate` flattens the whole utterance to English** — it does not preserve source languages.
- **This overturns the old "STT is a non-issue" note.** STT is an issue on synthetic mixed speech. **D-05 binds:** this says nothing about the user's real speech, and the failures cannot be split between Chatterbox and Whisper — especially since all Russian was synthesized without stress labeling (§6, permanent).

### What do the latency numbers imply for hardware? — **The Mac is not the ship class; buy against a TTS-dominated budget.** (with D-12)

Measured on Apple Silicon ([01-RESULTS.md §4, §5](.planning/phases/01-spike-gate/01-RESULTS.md)):
- Chatterbox warm TTFA for one short (~4 s) sentence: **6.27 s on `mps`, 21.70 s on `cpu`** (warm < cold on both). The same seed emits different audio lengths per backend, so the fair cross-device figure is RTF: **~1.6× on mps, ~3.0× on cpu.**
- A real WAV→WAV round trip is **~49 s warm-p50 wall**, and it is **TTS-dominated (~65%)**, STT ~34%, the local LLM **trivial (~1.4%)**. Chatterbox is the cost centre and the lever.
- **Interpretation (an inference, D-12):** a local round trip on this 18 GB Mac is far from conversational; the number exists to **size a purchase, not to claim the Mac ships**. On the Linux/CUDA target the STT and TTS stages would move to GPU — but that improvement is **unmeasured**. Do not quote 40–50 s as shipped latency, and do not quote a CUDA number that was not measured.
- **Two properties a buyer must budget for:** (a) Chatterbox latency is **sentence-dependent with a ~10× tail** (`alignment_stream_analyzer` runaway; needs a generation-time watchdog in the app), and (b) under sustained co-residence **warm ran slower than cold** on this 18 GB machine — the clearest signal that **18 GB is the binding constraint**.

---

## Agent-framework decision (SPIKE-05 / 06 / 07)

Recorded from [01-RESULTS.md §7](.planning/phases/01-spike-gate/01-RESULTS.md) / `raw/bakeoff-results.md`.

- **SPIKE-05 — Ollama token counts surface non-`None`: YES**, on both frameworks, read after stream aggregation. (LangChain exposes usage on only 1 of 334 streamed chunks, so a naive per-chunk read reports `None` 99.7% of the time — a reading-position issue, not a capability gap.)
- **SPIKE-06 — MCP tool args AND structured results surface through callbacks: YES**, on both frameworks, with **zero cloud**, verified byte-for-byte against the server's frozen fixture. CLAUDE.md's specific concern ("LangChain callbacks fail to cleanly surface MCP tool args + results") is **refuted** — though the failure mode it anticipated is real and exactly one `str()` call deep.
- **SPIKE-07 — which is easier to hide behind a port: NO DECISIVE WINNER, and saying so is the finding.** 245 vs 228 port lines (noise), **61 vs 61** lines of translation code (exact tie), **0 vs 0** framework types in a public signature. They differ in opposite directions: LangChain wins on coupling surface (4 vs 7 imported symbols), provider ergonomics (`init_chat_model` one-liner vs Provider+Model+mandatory `/v1`), and native local-first transport; Pydantic AI wins on trap density and error honesty (it raises on a truncated answer where LangChain returns it silently).

**Decision: the CLAUDE.md recommendation — LangChain 1.x + LangGraph — STANDS, but the basis has moved.**
- The named falsifier ("if MCP traces are opaque → switch to Pydantic AI") **fired negative**: LangChain's MCP traces are not opaque. No stated reason to switch survives.
- It no longer rests on superior observability (Pydantic AI is, if anything, slightly better there). It rests on coupling surface, provider ergonomics (which bear directly on the user-facing model-profile feature), a native local-first transport rather than an OpenAI-SDK shim, and release cadence.
- **Confidence: MEDIUM, unchanged** — but the open question is now "is a 4-vs-7 symbol coupling difference worth more than a lower trap density?", a judgement, not a measurement. The strongest open argument against remains the two `0.x` packages inside the LangChain 1.x tree (`langchain-mcp-adapters` 0.3.0 — the package that made SPIKE-06 pass — and `langchain-protocol` 0.0.18).
- **The cheap hedge is proven viable:** the port keeps zero framework types in its public signatures (test-enforced) at a measured cost of 61 translation lines on either framework. CLAUDE.md's rule (all framework imports confined behind the port, CI-enforced) is cheap and works — **if the choice is wrong, it is recoverable for ~250 lines.** That recoverability, more than the verdict, is the load-bearing result.
- **D-19 guard:** both adapters were completed; nothing is rejected on absence of evidence. Unbuilt and therefore unmeasured: LangGraph `interrupt()`→`confirm` tier, ordered fallback chains, multi-turn/retries/structured/streaming-tool output, `pydantic-ai-slim` 2.16.0. All deferred to Phase 3 (see [01-RESULTS.md §7](.planning/phases/01-spike-gate/01-RESULTS.md)).

---

## The Hebrew fallback ladder — NO RUNG SELECTED (D-10)

**Phase 1 exits with data only. No rung (A cloud-TTS-for-Hebrew, B experimental/degraded, C
STT-only, or "none") is selected here, and none may be, because the one input the choice requires
— the native-ear Hebrew verdict — does not exist (§2 above; 01-08 unexecuted).**

This is a deliberate constraint, not an omission (D-10): **Phase 6** designs the voice ports
including the per-language *engine* override, making it the last responsible moment to pick the
rung — and Phase 6 planning **cannot begin without selecting A/B/C/"none" from Phase 1's data.**
That data is currently incomplete. (Rung D — per-language voice switching — remains permanently
rejected per PROJECT.md and is not reopened.)

---

## Permanent facts recorded here (VOICE-12 and the Russian gap live in this file)

From [01-RESULTS.md §6](.planning/phases/01-spike-gate/01-RESULTS.md):
- **Chatterbox watermarking is unconditional (VOICE-12 / Pitfall 11).** `resemble-perth` watermarks every render; there is no flag to disable it; its cost is inside every latency number above. **This is the evidence of record for VOICE-12.**
- **Russian is synthesized without stress labeling — permanently.** `russian_text_stresser` is a permanent PyPI 404; not fixable by pip. Every Russian measurement in this phase, and any future D-20 Russian spot-check, carries this caveat.
- **faster-whisper (CTranslate2) is CPU-only on Apple Silicon** — no Metal backend. Relevant to why STT ran on cpu in the round trip.

---

## Open items still owed by a human (do not treat as resolved)

1. **SC#4 claim audit (this plan's Task 3, a `checkpoint:human-verify`).** A human must read every public claim in the repo — this file, any README, PROJECT.md's multilingual claims, doc drafts — against `01-RESULTS.md`, and edit down anything that exceeds the evidence, before the audit is "passed." This was NOT auto-approved. The automatable half is done: every claim above is drafted to trace to a specific measurement, and the two caveats are attached wherever their results are cited.
2. **The native-ear Hebrew verdict (SPIKE-01 / SPIKE-02, plan 01-08).** The irreplaceable human resource; still untaken. Blocks the D-10 rung selection.
3. **`dicta-onnx==1.0.9` supply-chain approval (01-03 Task 0).** The programmatic audit came back clean (repo real, identity matches, import hard-coded by chatterbox upstream), but the explicit human yes/no is still owed.
4. **The `dicta-onnx` license finding (L1).** The package declares **no license** on PyPI or GitHub — "all rights reserved" by default. Harmless for a throwaway spike, but it sits on the Hebrew critical path and **must be resolved before any Apache-2.0 shipping artifact depends on it** (raised for Phase 6 / packaging).

---

## No code from this phase survives (SC#5) — `spike/` is to be DELETED

Per SC#5 and D-18, **nothing written in Phase 1 carries forward except the recorded measurements
now living in `.planning/`** (the corpus fixture, the WAVs/transcripts/timings, `01-RESULTS.md`,
and this file). The throwaway measurement code, the three venvs, and the port sketch do not
survive: Phase 3 designs its port fresh from the findings (D-18), not from the sketch.

**`spike/` (repo root) is flagged for deletion.** Its only durable content — the provisioning
records, the raw write-ups, the corpus, and the bake-off findings — has been lifted into
`.planning/phases/01-spike-gate/` and into this file. Deleting `spike/` (including its
`.venv`s, `__pycache__`, `.pytest_cache`, and all harness `.py`) removes no evidence.

---

*Interpretation recorded 2026-07-25 for plan 01-10 (SPIKE-09). Links back to `01-RESULTS.md`,
committed first per D-09.*
