---
phase: 01-spike-gate
plan: 06
status: complete
tasks_completed: 3
tasks_total: 3
requirements: [SPIKE-05, SPIKE-06, SPIKE-07]
---

# 01-06 — Agent-framework bake-off

## Self-Check: PASSED

`uv run --python spike/bakeoff/.venv/bin/python pytest spike/ -q` → **171 passed** (95s).
Port conformance + artifact capture + trace handler: 41 passed.

## What was built

One PAAF-typed port (`spike/bakeoff/port.py`, stdlib-only, no framework imports)
implemented twice over the identical five-part surface — model loading from a named
profile, token streaming, one tool-call round trip, callback-driven tracing, and a
local MCP server.

| File | Role |
|---|---|
| `spike/bakeoff/port.py` | The port Protocol. Imports nothing. |
| `spike/bakeoff/adapter_langchain.py` | LangChain 1.3.14 implementation |
| `spike/bakeoff/adapter_pydantic_ai.py` | Pydantic AI 2.13.0 implementation |
| `spike/bakeoff/mcp_server/server.py` | 35-line local MCP server, two tools |
| `spike/bakeoff/test_port_conformance.py` | Enforces zero framework types in public signatures |
| `spike/bakeoff/test_artifact_capture.py` | SPIKE-06 structured-result capture |
| `spike/bakeoff/test_trace_handler.py` | Trace-layer contract |

Raw evidence: `.planning/phases/01-spike-gate/raw/bakeoff-results.md`.

**Both adapters were completed.** Nothing was abandoned under D-19's stopping rule, so
the SPIKE-07 verdict rests on comparison rather than on absence of evidence. §7 of the
raw results records what was deliberately left unexplored.

## Answers

**SPIKE-05 — do Ollama token counts come back non-`None`? YES, on both frameworks**,
on the streaming path, read after aggregation. 3/3 usage records populated on each.
A naive first-chunk read returns `null` on both — the `None` in CLAUDE.md is a
*read-at-the-wrong-moment* artifact, not a missing value.

**SPIKE-06 — are MCP tool args AND structured results visible through callbacks?
YES on both frameworks, with zero cloud.** Read from the tracing layer only
(`on_tool_start`/`on_tool_end`; `before_tool_execute`/`after_tool_execute`) — evidence
assembled outside the callbacks would have answered a different question. Verified
against the server's frozen fixture with a negative control proving the check can fail.

**SPIKE-07 — which is easier to hide behind a port? No decisive winner, and saying so
is the finding.** 61 vs 61 lines of private translation code — an exact tie on the
number that most directly answers what the boundary costs. 245 vs 228 total lines is
noise at this scale. Zero framework types reach a public signature on either side.

Model-loading was clearly easier to hide behind **LangChain** (`init_chat_model` is a
string→model factory that maps onto a YAML profile with no adapter logic). Tracing was
clearly easier to hide behind **Pydantic AI** (one prompt hook instead of two,
structured tool results already unwrapped, no way to read usage at the wrong moment).
Neither advantage carries the decision alone.

## Decision 1: the recommendation stands, on different grounds

CLAUDE.md rated Decision 1 MEDIUM and named one falsifier: *"if MCP traces are opaque
→ switch to Pydantic AI."* **That test ran and came back negative.** Tool args arrive
as a parsed dict; the full structured payload arrives in the artifact. The specific
stated reason to switch does not exist.

So LangChain stays — but no longer because of superior observability (Pydantic AI is
if anything slightly better there). It now rests on coupling surface (4 vs 7 imported
symbols), provider ergonomics, a native local-first transport rather than an OpenAI-SDK
shim, and release cadence (`pydantic-ai-slim` shipped 7 minors in 9 days against
`langchain`'s 8 patches in 43 days, still 1.3.x).

**Confidence: MEDIUM, unchanged — but the uncertainty moved.** It is no longer "can
LangChain see MCP traces?" It is now "is a 4-vs-7 symbol coupling difference worth more
than a lower trap density?" — a judgement call, not a measurement, and this spike does
not pretend to settle it. The two `0.x` packages inside the LangChain 1.x tree
(`langchain-mcp-adapters` 0.3.0, `langchain-protocol` 0.0.18) remain the strongest open
argument against — and `langchain-mcp-adapters` is the package that made SPIKE-06 pass.

## The load-bearing result

`port.py` is 400 lines and imports nothing. Both adapters keep zero framework types out
of its public signatures, enforced by a test that is demonstrably capable of failing.
CLAUDE.md's rule — confine framework imports to `paaf/_engine/`, enforced by a ruff
`banned-api` CI rule — is therefore cheap and it works. **If the choice is wrong, it is
recoverable for roughly 250 lines.** The decision does not have to be right the first time.

## Notable findings

**One framework difference favouring Pydantic AI, found by accident.** Ollama's default
`num_ctx` is 4096 while `qwen3.5:9b` declares 262144, so a reasoning-heavy prompt
exhausted the served context on both HTTP routes at the identical ceiling — a daemon +
model property the bake-off is not permitted to charge to either side. But **LangChain
returned the truncated answer silently** with `done_reason: "length"` buried in
`response_metadata`, where Pydantic AI raised `UnexpectedModelBehavior` and named the
remedy. Silent degradation is the worst property a voice assistant can have.

**The MCP target is locally authored on purpose** (`T-01-06-EOP`). A stdio MCP server is
a subprocess with the user's full privileges; nothing about this measurement needs a
third party's code. Its `room_status` tool returns a Pydantic model specifically so
FastMCP populates `structuredContent` — a probe whose tools returned only strings would
have sent no structured content, and a "not visible" answer would have been about the probe.

**Privacy asserted, not assumed** (§5 of raw results): no LangSmith, no Logfire,
Instrumentation deliberately left off on the Pydantic AI side.

## Deferred — Human Action Required

None originating in this plan; all three tasks were `type="auto"`.

Still owed from earlier plans:
- **`dicta-onnx` supply-chain approval** (01-03 Task 0) — evidence in `raw/voice-provision.md`.
- **Blind native-ear Hebrew verdict** (01-08) — 46 clips rendered and untouched.

## Deviations

Executed under a partial-resume: Tasks 1–2 were committed in an earlier pass
(`740d171`, `d58ef97`); Task 3 was verified against disk and committed as `8a32bf2`.
The plan's `<verify>` uses `uv run pytest`, which fails in this repo — there is
deliberately no root `pyproject.toml`. Canonical form is
`uv run --python spike/bakeoff/.venv/bin/python pytest spike/ -q`.

**SPIKE-07 marked; SPIKE-05/SPIKE-06 answered here but left for 01-10 to record** in
DECISIONS.md, which is where the measured reality is supposed to land (D-09).
