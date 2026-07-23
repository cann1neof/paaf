---
phase: 01-spike-gate
plan: 04
subsystem: bakeoff
tags: [ollama, qwen3.5, langchain, pydantic-ai, tool-calling, privacy, telemetry, venv-isolation]

# Dependency graph
requires:
  - "01-01: spike/ quarantine, spike/pytest.ini, the two-venv split, .gitignore over venvs and weights"
provides:
  - "Ollama 0.32.1 daemon running on 127.0.0.1:11434 — unblocks SPIKE-05/06/07/08, four of nine requirements"
  - "qwen3.5:9b (capability, 9.7B Q4_K_M) and qwen3.5:2b (latency, 2.3B Q8_0) pulled, digests recorded, Apache-2.0"
  - "TOOL-CALL GATE GREEN — 30/30 well-formed tool calls, 100% in every condition, both models, both paths"
  - "spike/bakeoff/.venv — isolated Python 3.12 bake-off env (92 packages, langchain 1.3.14 / pydantic-ai-slim 2.13.0), git-ignored"
  - "spike/bakeoff/tool_call_sanity.py — 7-condition validator, 2 probes, env assertions, CLI report"
  - "spike/bakeoff/test_tool_call_sanity.py (39 tests: 32 fast incl. 10 negative controls, 7 slow live gate)"
  - "spike/bakeoff/conftest.py + __init__.py — collection guard and conftest-shadowing fix"
  - "Verified telemetry-off posture (PRIV-02): 9 env vars unset AND the installed exporters proven inert at runtime"
  - ".planning/phases/01-spike-gate/raw/bakeoff-provision.md — full provisioning + gate record"
affects: [01-06, 01-07, 01-08, 01-09, 01-10]

# Tech tracking
tech-stack:
  added: [ollama 0.32.1, qwen3.5:9b, qwen3.5:2b, langchain 1.3.14, langchain-core 1.5.0, langgraph 1.2.9, langchain-ollama 1.1.0, langchain-mcp-adapters 0.3.0, pydantic-ai-slim 2.13.0, mcp 1.28.1, fastmcp-slim 3.4.4, ollama-py 0.6.2]
  patterns:
    - "Capability gate before comparison: prove the instrument works before it is used to judge anything"
    - "Negative controls as a first-class layer — ten malformed inputs the validator must reject, each for a stated reason"
    - "Vacuity check on every guarantee: an empty capability list is an ERROR, never read as 'the bad thing is absent'"
    - "Telemetry assertions target runtime state, not env vars — the exporters ship as hard transitive deps"
    - "Package-ify a spike subdirectory (__init__.py) so its conftest cannot shadow the parent's"

key-files:
  created:
    - spike/bakeoff/tool_call_sanity.py
    - spike/bakeoff/test_tool_call_sanity.py
    - spike/bakeoff/conftest.py
    - spike/bakeoff/__init__.py
    - .planning/phases/01-spike-gate/raw/bakeoff-provision.md
  modified: []
  deleted: []

key-decisions:
  - "The roadmap's `qwen3` tag is stale: it is no longer in the top-20 tool-capable models. qwen3.5 replaces it; qwen3.6 is disqualified because its ladder starts at 27b/17GB on an 18GB machine"
  - "Two models pulled — qwen3.5:9b for SPIKE-05/06/07 capability, qwen3.5:2b for SPIKE-08 latency (must be co-resident with Whisper ~3GB + Chatterbox ~3.2GB inside 18GB). Both gated; the small one is not exempt"
  - "Explicit tags everywhere, never `latest` — a moving tag is not reproducible and D-07 promises Phase 7 can re-run this"
  - "Held pydantic-ai-slim at 2.13.0 rather than taking today's 2.16.0: RESEARCH read the 2.13.0 wheel, so 2.16.0 would make any SPIKE-07 failure ambiguous between framework awkwardness and a stale snippet"
  - "Detached `ollama serve`, NOT `brew services` — a launchd agent would survive `rm -rf spike/` and weaken 01-01's SC#5 one-`ls` property"
  - "Stock Ollama config, refusing Homebrew's suggested OLLAMA_FLASH_ATTENTION/KV-cache tuning — SPIKE-08 must describe what a user gets"
  - "The gate runs at stock sampling defaults (temperature 1), not a tuned harness, for the same reason"
  - "SPIKE-07 deliberately left unchecked: this plan provisions and proves the instruments, plan 01-07 renders the bake-off verdict"

patterns-established:
  - "Gate-the-instrument-before-the-experiment: A5 says a weak tool-caller would sink SPIKE-06 for reasons unrelated to the framework, so the model is falsified first"
  - "Selection-not-just-emission: two cases, one per tool, so a model that always calls the same tool scores 50% instead of 100%"
  - "Self-retiring workarounds: the test that documents the ollama-client defect fails once upstream fixes it"

requirements-completed: []

coverage:
  - id: D1
    description: "The Ollama daemon runs locally on loopback and a named, tool-calling-capable model is pulled with its digest recorded"
    requirement: "SPIKE-07"
    verification:
      - kind: integration
        ref: "curl -sf http://127.0.0.1:11434/api/tags; test_tool_call_sanity.py::test_ollama_daemon_is_reachable, ::test_model_is_pulled_and_tool_capable[qwen3.5:9b|qwen3.5:2b]"
        status: pass
    human_judgment: false
  - id: D2
    description: "The chosen model emits a WELL-FORMED tool call (correct name + schema-valid, type-correct, value-correct args) on a trivial two-tool case, reliably rather than once"
    requirement: "SPIKE-07"
    verification:
      - kind: integration
        ref: "test_tool_call_sanity.py::test_capability_model_emits_well_formed_tool_calls[raw|langchain][add|get_time], ::test_latency_model_also_emits_well_formed_tool_calls — 100% over 5 trials each"
        status: pass
    human_judgment: false
  - id: D3
    description: "The gate is not vacuous: ten malformed tool calls are rejected, each for its stated reason, and correct calls are still accepted"
    requirement: "SPIKE-07"
    verification:
      - kind: unit
        ref: "test_tool_call_sanity.py::test_validator_rejects_malformed_tool_calls (10 ids), ::test_validator_accepts_the_correct_call (2 ids)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The bake-off venv is Python 3.12, isolated from the voice venv in both directions, and has langchain + pydantic-ai v2 + mcp-adapters installed and importing at the recorded pins"
    requirement: "SPIKE-07"
    verification:
      - kind: integration
        ref: "8/8 import smoke under spike/bakeoff/.venv; cross-venv absence check (no torch/chatterbox here, no langchain/pydantic-ai there); raw/bakeoff-provision.md §2.1-2.3, §2.7-2.8"
        status: pass
    human_judgment: false
  - id: D5
    description: "Telemetry is off at BOTH levels — env vars unset, and the installed langsmith/logfire-api exporters proven inert at runtime (PRIV-02, T-01-04-TEL)"
    requirement: "SPIKE-07"
    verification:
      - kind: unit
        ref: "test_tool_call_sanity.py::test_telemetry_env_var_is_unset (9 ids), ::test_assert_telemetry_off_passes_in_this_environment, ::test_langsmith_and_logfire_are_present_but_inert"
        status: pass
    human_judgment: false
  - id: D6
    description: "Inference is local-only: no pulled tag declares the `cloud` capability, and the check that asserts this cannot pass vacuously"
    requirement: "SPIKE-07"
    verification:
      - kind: unit
        ref: "test_tool_call_sanity.py::test_model_is_local_only_not_cloud_routed, ::test_capabilities_are_non_empty_so_the_no_cloud_check_is_not_vacuous, ::test_ollama_client_list_really_does_drop_capabilities"
        status: pass
    human_judgment: false

# Metrics
duration: 25min
completed: 2026-07-23
status: complete
---

# Phase 1 Plan 04: Bake-off Provisioning & Tool-Call Gate Summary

**The tool-call gate is GREEN — 30/30 well-formed calls, 100% in every condition — so assumption A5 holds and SPIKE-06's verdict will be about the frameworks rather than about a weak model. Getting there overturned the roadmap's model default, quantified pydantic-ai's release cadence as 7 minors in 9 days against LangChain's 8 patches in 43, and caught a no-cloud privacy assertion that was passing vacuously for every model.**

## Gate Verdict

| Question the plan asked | Answer |
|---|---|
| **Is the tool-call gate green?** | **YES** — 100% (5/5) in all six conditions, 30 well-formed calls out of 30 |
| Which model? | **`qwen3.5:9b`** (capability) and **`qwen3.5:2b`** (latency), both `tools`-capable, both Apache-2.0 |
| Was a model swap needed? | **No.** Both cleared the gate on the first attempt |
| Is the daemon up? | Yes — Ollama **0.32.1** on `127.0.0.1:11434`, loopback only |
| Is the bake-off venv isolated? | Yes — proven in **both** directions, not just asserted |
| Is telemetry off? | Yes — 9 env vars unset **and** the installed exporters proven inert at runtime |
| Is inference local-only? | Yes — no `cloud` capability on either tag, via a check that can no longer pass vacuously |

## Performance

- **Duration:** ~25 min (11:13Z → 11:38Z)
- **Tasks:** 3
- **Files created:** 4 source files + 1 planning record (555 lines)
- **Tests:** 39 in the bake-off venv (32 fast, 7 slow); 61 base and 70 voice re-verified green
- **Downloaded:** 8.7 GB of model weights, both pulls explicit and announced (`T-01-04-DL`)

## The Model Decision — the re-check changed the answer

CLAUDE.md §Decision 6 marks the community default `[UNVERIFIED — MEDIUM]` and instructs
re-checking at implementation time rather than taking the roadmap's word. That instruction
paid for itself:

- **Plain `qwen3` — the tag RESEARCH's own code example uses (`init_chat_model("ollama:qwen3")`) — is no longer in the top 20 tool-capable models on the Ollama library.** The Qwen3 *family* recommendation survives; the specific tag does not.
- **`qwen3.6` exists** and did not when CLAUDE.md was written — but its size ladder starts at **27b / 17 GB**, leaving nothing for Whisper and Chatterbox on an 18 GB machine. Disqualified on hardware, a clean and checkable exclusion rather than a taste judgement.
- **`qwen3.5`** is the highest-ranked tool-capable Qwen3-family model, declares `tools`, spans 0.8b→122b so it covers both the capability and latency needs, and is **Apache-2.0**. That last point is not incidental: 01-03 put an **unlicensed** package (`dicta-onnx`, L1) on the Hebrew critical path, so license hygiene on critical-path artifacts is a live concern in this phase now.

Two models were pulled per RESEARCH Open Q1: `qwen3.5:9b` for the bake-off's capability
demands and `qwen3.5:2b` for SPIKE-08, where the LLM must sit alongside Whisper (~3 GB) and
Chatterbox (~3.2 GB) — 2.7 + 3 + 3.2 ≈ 8.9 GB, comfortably inside 18 GB. **Both were gated.**
An unmeasured latency model could contribute a tool-call failure to SPIKE-08 that would read
as a pipeline problem.

Selection rested on tool-calling capability and memory fit. Nothing here scores prose.

## The Finding That Justifies the Gate's Design

The first run of the fast suite **failed**, on this:

```
AssertionError: model 'qwen3.5:9b' does not declare the 'tools' capability: []
```

The `ollama` python client 0.6.2 models the `/api/tags` response with a pydantic schema
whose `Model` class declares only `model / modified_at / digest / size / details` — **no
`capabilities` field.** The daemon *does* send `capabilities` (confirmed against the raw
HTTP endpoint), but pydantic drops the unknown key, so `client.list()` returns `[]` for
every model.

The consequence is worse than a wrong assertion message. The PRIV-02 no-cloud guard was:

```python
if "cloud" in caps:   # caps is always [] -> never true
    raise AssertionError(...)
```

**It would have passed for every tag, including a genuinely cloud-routed `qwen3.5:cloud`.**
The `qwen3.5` family really does publish `qwen3.5:cloud` and `qwen3.5:397b-cloud`, and the
family advertises `cloud` among its capabilities — those tags route inference to Ollama's
hosted service while looking exactly like a local call. A privacy guarantee that is
vacuously true is worse than none, because it reads as evidence.

`capabilities_of()` now reads `/api/show` (whose schema *does* declare `capabilities`) and
treats an empty list as an **error**, never as "the bad thing is absent". Two regression
tests pin it, one of which fails deliberately when a future `ollama` client adds the field,
so the workaround retires itself rather than rotting into a stale comment.

This is the same *class* of defect as 01-03's dicta finding: it lives in the interaction
between two packages' schemas and is invisible to reading either one.

## Measured Results

### The gate — 30/30, at stock defaults

```
host=http://127.0.0.1:11434  trials=5  min_reliability=1.0

=== qwen3.5:9b  caps=['completion', 'vision', 'tools', 'thinking'] ===
  [PASS] raw       add       100% (5/5)  mean   5.3s
  [PASS] raw       get_time  100% (5/5)  mean   3.8s
  [PASS] langchain add       100% (5/5)  mean   5.2s
  [PASS] langchain get_time  100% (5/5)  mean   3.5s

=== qwen3.5:2b  caps=['completion', 'vision', 'tools', 'thinking'] ===
  [PASS] langchain add       100% (5/5)  mean   2.8s
  [PASS] langchain get_time  100% (5/5)  mean   1.8s

GATE: GREEN
```

Run at the family's **stock** sampling defaults (`temperature 1`, `top_p 0.95`, `top_k 20`,
`presence_penalty 1.5`) — not a tuned harness. Temperature 1 is high for tool-call
determinism, which is exactly why the gate repeats each case five times: a single success
at temperature 1 is a coin flip, and only a rate is evidence.

Both the raw `ollama` client and `init_chat_model("ollama:…")` are exercised, because
RESEARCH §Pitfall 8 warns against concluding anything about Ollama through a framework
without checking the provider first. They agreed on every trial; a disagreement would have
been a finding about the adapter.

### "Well-formed" is seven checks, not `if response.tool_calls:`

A model emitting `add` with `{"a": "48271"}` — stringified, missing `b` — has emitted a
tool call and passes the naive check. The validator requires: exactly one call; a bound
tool name; the **expected** name; dict args; a successful JSON round trip; exact key match
in both directions; and correct types **and values**, with `bool` explicitly excluded from
`integer` because Python's `isinstance(True, int)` is `True`.

Two cases, one per tool, so the gate measures tool **selection**: a model that always calls
`add` scores 50% here where a single-case gate would score 100%.

### The gate is proven capable of failing

Per 01-03's rule — *a gate that cannot fail manufactures confidence* — **ten negative
controls** feed hand-built malformed calls to the validator and require rejection *for the
stated reason*: prose, two calls, hallucinated name, wrong tool, args as a JSON string,
missing required arg, extra arg, stringified integer, bool-as-integer, right-shape-wrong-values.
Two complementary tests require a correct call to be **accepted**, since a validator that
rejects everything is equally useless. `validate_tool_call` takes a framework-free
`[{"name", "args"}]` shape, which is what makes those controls possible without model
traffic — they run in 0.12 s against the live gate's 88 s.

### Informational, carried to SPIKE-05 — token counts are NOT `None`

CLAUDE.md lists *"token counts come back `None` for Ollama"* as a rough edge and a reason
its LangChain recommendation is only MEDIUM confidence. Measured on the **non-streaming**
path at both levels:

| Path | Field | Value |
|---|---|---|
| raw `ollama` client | `prompt_eval_count` / `eval_count` | **364 / 110** |
| `init_chat_model("ollama:…")` | `usage_metadata` | **`{'input_tokens': 346, 'output_tokens': 115, 'total_tokens': 461}`** |

`langchain-ollama` 1.1.0 maps `prompt_eval_count`/`eval_count` into `usage_metadata`
exactly as RESEARCH read from the wheel. **This does not close SPIKE-05** — Pitfall 8 says
the `None` appears on the *streaming* path, which SPIKE-05 owns. Following 01-03's pattern
this check is informational: the test asserts only that the fields exist and prints their
values, so a negative answer would be a finding to carry forward, not a gate failure.

### Free finding for Decision 1 — release cadence, from the release feed

Re-verifying the pins produced evidence bearing directly on the bake-off's stability axis:

| `pydantic-ai-slim` | | `langchain` | |
|---|---|---|---|
| 2.10.0 → **2.16.0** | 2026-07-15 → 2026-07-23 | 1.3.7 → **1.3.14** | 2026-06-10 → 2026-07-16 |
| **7 MINOR releases in 9 days** | | **8 PATCH releases in 43 days, still 1.3.x** | |

CLAUDE.md scores "API stability history" as a decision axis and cites pydantic-ai
shortening its no-breaking-change window from six months to three. This is the same fact
observed from the release feed rather than from the vendor's blog post. **Carry it into
01-10's DECISIONS.md.**

## Task Commits

| Task | Commit | Type |
|---|---|---|
| Task 1 — Ollama install, daemon, model selection + pull, telemetry assertion | `90e8c2d` | chore |
| Task 2 — isolated bake-off venv at exact pins, resolved freeze | `d865b84` | chore |
| Task 3 — tool-call sanity gate (module, 39 tests, conftest, `__init__.py`) | `5f743e5` | feat |

**Plan metadata:** see the `docs(01-04)` commit following this SUMMARY.

## Test Results

| Suite | Venv | Tests | Result |
|---|---|---:|---|
| `spike/bakeoff/` fast (`-m "not slow"`) | bake-off | 32 | pass (0.12 s) |
| `spike/bakeoff/` full (incl. live gate) | bake-off | **39** | **pass (88 s)** |
| Plan's literal target `test_tool_call_sanity.py` | bake-off | 39 | pass (85 s) |
| Full quarantine `spike/` | base | **61** | **pass (0.34 s)** — restored, see deviation 3 |
| `spike/voice/` fast | voice | 70 | pass (3.9 s) — unaffected |

## Assumptions & Open Questions Resolved

| Ref | Claim | Outcome |
|---|---|---|
| **A5** | An Ollama model can be found that tool-calls reliably enough for SPIKE-06/07 on 18 GB | ✅ **Confirmed.** 100% over 30 trials on a trivial two-tool case, both models, both paths. |
| **OQ 1** | Which Ollama model for the bake-off? | ✅ **Resolved** — `qwen3.5:9b` capability + `qwen3.5:2b` latency, chosen on tool-calling and memory fit, verified before SPIKE-06 as the recommendation required. |
| CLAUDE.md | "Token counts come back `None` for Ollama" | ⚠️ **Refuted for the non-streaming path** at both levels. Streaming remains open and belongs to SPIKE-05. |
| CLAUDE.md | "Qwen3 family sized to VRAM is the standing default" | ⚠️ **Family holds, tag is stale.** `qwen3` has fallen out of the top-20 tool-capable models; `qwen3.5` supersedes it. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] The plan's four telemetry variables are not sufficient**

- **Found during:** Task 1
- **Issue:** The plan names `LOGFIRE_TOKEN`, `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGCHAIN_TRACING_V2`. Those are necessary but do not close the egress surface. `LANGCHAIN_API_KEY` is the pre-1.0 name still honoured by langsmith-sdk; `LANGSMITH_ENDPOINT` redirects traces; and — the significant one — **pydantic-ai's egress path is OpenTelemetry, not a Logfire-branded variable**, so `OTEL_EXPORTER_OTLP_ENDPOINT` can export spans with every named variable unset. A four-variable audit would have declared PRIV-02 satisfied while leaving the pydantic-ai half of the bake-off able to export.
- **Fix:** Audited **nine** variables, and made the list a module constant (`TELEMETRY_ENV_VARS`) parametrized into nine tests, so it is enforced on every run rather than checked once by hand.
- **Verification:** all nine unset; whole-environment `env | grep -iE 'langsmith|langchain|logfire|otel'` returns nothing.
- **Commits:** `90e8c2d`, `5f743e5`

**2. [Rule 2 - Missing Critical] Both telemetry exporters are physically installed, so an env-var audit alone cannot establish PRIV-02**

- **Found during:** Task 2
- **Issue:** `langchain` pulls **`langsmith==0.10.10`** and `pydantic-ai-slim` pulls **`logfire-api==4.38.0`** and **`opentelemetry-api==1.44.0`** as hard transitive dependencies. They are in the venv whether or not anyone wants them. The threat register's `T-01-04-TEL` is about *egress*, and a set of unset variables is an argument about egress, not an observation of it.
- **Fix:** Added runtime-state assertions: `langsmith.utils.tracing_is_enabled()` is `False`, and the **real `logfire` package is absent** — only the `logfire-api` no-op shim is installed. Recorded the standing rule for 01-05/06/07: *do not `pip install logfire`, do not call `logfire.configure()` or `Agent(..., instrument=True)`* — installing real `logfire` converts the shim into a live exporter with no env var changing.
- **Verification:** `test_langsmith_and_logfire_are_present_but_inert` passes.
- **Commits:** `d865b84`, `5f743e5`

**3. [Rule 1 - Bug] The new `spike/bakeoff/conftest.py` shadowed `spike/conftest.py` and broke the entire base suite**

- **Found during:** Task 3 regression check
- **Issue:** pytest's default `prepend` import mode inserts `spike/bakeoff/` into `sys.path` and imports its conftest under the plain top-level name `conftest` — which `spike/conftest.py` already claims. Collection is alphabetical and `bakeoff` sorts *before* `test_fixtures_smoke.py`, so the bake-off conftest won and 01-01's `from conftest import FakeModel, FakeTool` resolved to the wrong file: `ImportError: cannot import name 'FakeModel' from 'conftest' (.../spike/bakeoff/conftest.py)`. pytest treats a collection error as fatal for the whole run, so the 61 stdlib-only tests from 01-01/01-02 went from `61 passed` to `1 error`. This is 01-03's regression in a new disguise — and note that `spike/voice/` escaped it **only because `voice` sorts after `test_fixtures_smoke.py`**, which is alphabetical luck rather than design.
- **Fix:** Added `spike/bakeoff/__init__.py`. With it present, pytest walks up to the first non-package directory (`spike/`), puts *that* on `sys.path`, and imports the conftest as `bakeoff.conftest` — a distinct module name. `spike/conftest.py` keeps the plain `conftest` name and 01-01's import is correct again. `test_tool_call_sanity.py` correspondingly imports `from bakeoff.tool_call_sanity import …`. The file is 33 lines of explanation, not an empty marker, because the next person to see an empty `__init__.py` in a spike tree will delete it.
- **Why not the alternatives:** `--import-mode=importlib` would have fixed it globally but would break both 01-01's `from conftest import …` and 01-03's `import gate_readiness`. Moving 01-01's doubles into a `fakes.py` would have worked but rewrites another plan's files to fix damage this one caused.
- **Verification:** base venv `pytest spike/ -q` → `61 passed`; bake-off `pytest spike/bakeoff/ -q` → `39 passed`; voice `70 passed`.
- **Commit:** `5f743e5`

**4. [Rule 1 - Bug] The no-cloud assertion was vacuously true — see "The Finding That Justifies the Gate's Design"**

- **Found during:** Task 3, first fast-suite run
- **Fix:** `capabilities_of()` reads `/api/show` instead of `client.list()`, and raises on an empty capability list rather than reading empty as "no cloud capability". Two regression tests, one self-retiring.
- **Verification:** `test_capabilities_are_non_empty_so_the_no_cloud_check_is_not_vacuous` and `test_ollama_client_list_really_does_drop_capabilities` pass.
- **Commit:** `5f743e5`

### Deliberate departures from the plan text

**5. `pydantic-ai-slim` held at 2.13.0 although 2.16.0 shipped today**

The plan says to install exact pins and *"if a newer patch is current, record BOTH."* The
drift is larger than a patch: three minors in the five days since RESEARCH. **2.13.0 was
installed deliberately** — RESEARCH established the v2 MCP surface (`MCPToolset`,
`MCPToolsetClient`, `_build_transport`, the capabilities primitive) by reading the *2.13.0
wheel source*. On 2.16.0, any SPIKE-07 difficulty would be ambiguous between "the framework
is awkward" and "our snippet is three minors stale", which is precisely the misattribution
this plan exists to prevent. Both versions are recorded; 01-07 owns whether to re-test
against 2.16.0.

**6. `langchain-core` resolved forward to 1.5.0, not the 1.4.9 RESEARCH read — re-verified rather than accepted**

`langchain==1.3.14` does not pin `langchain-core` exactly. RESEARCH's central SPIKE-05/06
finding — *"CHAT models fire `on_chat_model_start`, NOT `on_llm_start`; implement BOTH"* —
was read from the 1.4.9 wheel, so silently accepting 1.5.0 would leave that finding
unverified at the exact point SPIKE-05 depends on it. All six `AsyncCallbackHandler` hooks
were re-checked against the installed 1.5.0 and **all six survive with the recorded
signatures**. RESEARCH's `SpikeTrace` handler is valid against the installed tree.

**7. Detached `ollama serve`, not `brew services start ollama`**

Homebrew's suggested `brew services` installs a launchd agent that starts at login and
would **survive `rm -rf spike/`** — a Phase-1 artifact outside the quarantine, directly
weakening 01-01's SC#5 one-`ls` property. A detached `nohup ollama serve` is the disposable
equivalent. Restart instructions are in `raw/bakeoff-provision.md` §1.2. Homebrew's suggested
`OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0` tuning was likewise declined: SPIKE-08
must describe stock Ollama, not a tuned build.

### Deliberate non-action

**8. `SPIKE-07` was NOT marked complete in REQUIREMENTS.md**

The plan's frontmatter lists `requirements: [SPIKE-07]`, but SPIKE-07 reads *"Agent-framework
bake-off (LangChain/LangGraph vs Pydantic AI) judged on one criterion: which is easier to hide
behind a port."* No bake-off has been run and no port has been written. This plan provisions
and **proves the instruments**; plan `01-07` renders the verdict. Checking the box now would
put a false claim into the traceability matrix that the SC#4 claim audit exists to catch —
the same reasoning 01-01 applied to SPIKE-09 and 01-03 applied to SPIKE-01/02.
`requirements-completed: []` reflects that. **01-07 should mark SPIKE-07 complete.**

---

**Total deviations:** 4 auto-fixed (2 bugs, 2 missing-critical), 3 deliberate departures, 1 deliberate non-action.
**Impact on plan:** No scope creep. Two deviations closed real privacy gaps the plan's own checklist would have left open; one repaired damage this plan's new conftest did to a prior plan's guarantee; one fixed a guarantee that was passing vacuously. Every plan acceptance criterion passes verbatim.

## Issues Encountered

- **The gate found its first real defect in its own probe, before touching a model.** That is the argument for negative controls in compressed form: the ten malformed-input tests took minutes to write and the vacuous-capability bug would otherwise have shipped as a green privacy assertion into 01-06 through 01-10.
- **Alphabetical ordering was load-bearing and nobody knew.** `spike/voice/` avoided the conftest-shadowing bug purely because `voice` > `test_fixtures_smoke.py`. Any later plan adding a `spike/a*/` or `spike/m*/` directory with a conftest will hit it. See carried concerns.
- **Both models are `thinking` models.** They emit a reasoning pass before the tool call, in a separate `thinking` field rather than mixed into `content`, so a tracer will not mistake reasoning for a malformed call. But SPIKE-08's time-to-first-token will include think tokens unless thinking is disabled — 01-09 must decide that deliberately and state which it measured.
- **`langchain-protocol==0.0.18` sits inside the LangChain 1.x dependency tree.** Worth putting next to `langchain-mcp-adapters==0.3.0` when 01-10 weighs the "LangChain is the stable one" claim: two `0.x` packages under a 1.x stability promise.

## Known Stubs

None. Every artifact is complete for its stated purpose. `tool_call_sanity.py` deliberately
tests only two trivial tools and does not touch MCP — MCP tracing is SPIKE-06's, gated
behind this plan by design (A5).

## Deferred — Human Action Required

**1. No blocking human checkpoint arose in this plan.** All three tasks were `type="auto"`
and the plan is `autonomous: true`. The one judgment-adjacent step — model selection, which
CLAUDE.md flags `[UNVERIFIED]` — was resolved on stated, checkable grounds (library ranking,
declared `tools` capability, the 18 GB memory bound, Apache-2.0 licensing) and then
**falsified empirically** by the gate rather than asserted. The reasoning is in
`raw/bakeoff-provision.md` §1.3 if it warrants a second opinion.

**2. Carried from 01-03, still owed:** the `dicta-onnx==1.0.9` supply-chain approval and the
L1 unlicensed-dependency ruling. Untouched by this plan. Noted because this plan's model
choice weighted Apache-2.0 licensing partly *because* of it.

**3. Situational awareness — human-gated items still ahead in this phase:** the native-ear
Hebrew verdict (SPIKE-02 / D-13, blind per D-14), the Russian/Spanish spot-checks (D-20),
and the SC#4 claim audit (SPIKE-09). None belong to this plan.

## User Setup Required

None — no accounts, no credentials, no external services. Ollama runs entirely locally on
loopback; both models are public and Apache-2.0; `HF_TOKEN` remains deliberately unset.

**One operational note:** the daemon is a detached process, not a launchd service, so **it
does not survive a reboot**. Any later plan that finds `127.0.0.1:11434` unreachable should
restart it rather than treat it as a provisioning failure:

```bash
nohup /opt/homebrew/bin/ollama serve > /tmp/paaf-ollama/serve.log 2>&1 &
curl -sf http://127.0.0.1:11434/api/tags   # expect 200
```

## Next Phase Readiness

**Ready. The bake-off instruments are provisioned and proven.** Binding instructions for the
plans that inherit from this one:

1. **Use the pinned tags, never `latest`** — `qwen3.5:9b` for SPIKE-05/06/07, `qwen3.5:2b` for SPIKE-08. Digests are in `raw/bakeoff-provision.md` §1.4.
2. **Run under `spike/bakeoff/.venv`**, never the voice venv. Canonical command: `uv run --python spike/bakeoff/.venv/bin/python pytest spike/bakeoff/ -q`.
3. **Do not `pip install logfire`** and do not pass `instrument=True` / call `logfire.configure()`. The venv currently holds a no-op shim; installing the real package converts it into a live exporter with no env var changing.
4. **New modules in `spike/bakeoff/` must import as `bakeoff.<module>`**, because the directory is a package (see deviation 3).
5. **For SPIKE-05:** the non-streaming answer is already known and positive (§Measured Results). The open question is the streaming path — RESEARCH §Pitfall 8 says do not conclude `None` from a streaming chunk; check `on_llm_end`, where usage lives on the final result. RESEARCH's `SpikeTrace` handler is verified valid against the installed `langchain-core` **1.5.0**.
6. **For SPIKE-07:** `pydantic-ai-slim` is at **2.13.0**, whose wheel RESEARCH read. `MCPServerStdio`/`MCPServerSSE`/`MCPServerStreamableHTTP` do not exist in v2 — use `MCPToolset`. Decide explicitly whether the drift to 2.16.0 needs re-testing.
7. **For SPIKE-06:** both adapters share `mcp==1.28.1`, so the comparison is against one protocol version. Node v24.16.0 is present for a stdio server.

**Carried concerns:**

- **The conftest-shadowing trap is not fully closed.** `spike/voice/` is safe only by alphabetical accident. Any future `spike/<dir-sorting-before-test_fixtures_smoke.py>/conftest.py` will break the base suite the same way. The durable fix is to move 01-01's `FakeModel`/`FakeTool` into a `spike/fakes.py` with a unique module name; that was out of scope here because it rewrites another plan's files to fix damage this one caused.
- **The daemon does not survive a reboot** (deliberate — see User Setup Required).
- **Both models are `thinking` models**; SPIKE-08 must state whether think tokens are inside or outside its time-to-first-token.
- **`langsmith` and `logfire-api` are installed** and will remain so. The posture is enforced by tests, not by absence — if a later plan drops those tests, PRIV-02 becomes an unverified claim again.
- Carried unchanged from 01-03: **`dicta-onnx` is unlicensed and on the Hebrew critical path** (Phase 6 / packaging risk).

## Self-Check: PASSED

Files verified present on disk:

- `spike/bakeoff/tool_call_sanity.py` — FOUND (491 lines)
- `spike/bakeoff/test_tool_call_sanity.py` — FOUND (292 lines)
- `spike/bakeoff/conftest.py` — FOUND (86 lines)
- `spike/bakeoff/__init__.py` — FOUND (33 lines)
- `.planning/phases/01-spike-gate/raw/bakeoff-provision.md` — FOUND (555 lines)

Commits verified in `git log`: `90e8c2d`, `d865b84`, `5f743e5` — all FOUND.

Plan verification commands re-run at self-check time, all green:

- Task 1: `curl -sf http://127.0.0.1:11434/api/tags && grep -qiE 'model' raw/bakeoff-provision.md` → exit 0
- Task 2: `grep -qiE 'langchain==1\.3' … && grep -qiE 'pydantic-ai-slim.*2\.13' … && grep -qiE 'langchain-mcp-adapters==0\.3\.0' …` → exit 0
- Task 3: `uv run --python spike/bakeoff/.venv/bin/python pytest spike/bakeoff/test_tool_call_sanity.py -q` → **39 passed in 84.56s**, exit 0
- Regression: base `61 passed`, voice `70 passed` (fast) — both restored/unaffected

No unintended deletions: `git diff --diff-filter=D HEAD~1 HEAD` empty on every task commit. No
venv or model weight is tracked — `git check-ignore` confirms `spike/bakeoff/.venv/`, and
`git status --porcelain -- spike/` is clean after commit.

---
*Phase: 01-spike-gate*
*Completed: 2026-07-23*
