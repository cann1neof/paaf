# Phase 1 — Agent-Framework Bake-off: raw results

**Requirements answered:** SPIKE-05 (Ollama token counts), SPIKE-06 (MCP tool args +
structured results through callbacks), SPIKE-07 (which framework is easier to hide behind
a port).

**Method (D-15/D-16):** one PAAF-typed port (`spike/bakeoff/port.py`, stdlib-only)
implemented twice — `adapter_langchain.py` and `adapter_pydantic_ai.py` — over the *same*
five-part surface: load a model from a named profile, stream tokens, one tool-call round
trip, callback-driven tracing, and an MCP server. SPIKE-05 and SPIKE-06 are read out of the
port's trace layer, not measured beside it. **Both adapters were completed.** Nothing was
abandoned under D-19's stopping rule; §7 records what was deliberately left unexplored.

**These interface signatures do not survive (D-18).** Only the findings below carry.

---

## 0. Conditions

| | |
|---|---|
| Date | 2026-07-23 |
| Machine | Apple Silicon Mac, 18 GB unified memory (dev harness only; Linux is the ship target) |
| Ollama | 0.32.1, detached `ollama serve`, `127.0.0.1:11434` (loopback only) |
| Model | **`qwen3.5:9b`** — the capability model 01-04 gated at 30/30 well-formed tool calls |
| Python | 3.12.13, `spike/bakeoff/.venv` |
| LangChain | `langchain` 1.3.14 · `langchain-core` 1.5.0 · `langchain-ollama` 1.1.0 · `langchain-mcp-adapters` 0.3.0 |
| Pydantic AI | `pydantic-ai-slim` **2.13.0** — held deliberately by 01-04 (RESEARCH read this wheel) |
| MCP | `mcp` 1.28.1 for **both** sides, so the comparison is against one protocol version |
| Telemetry | asserted at runtime in both probes — see §5 |

### The MCP target — locally authored, on purpose

`spike/bakeoff/mcp_server/server.py`, 35 code lines, two tools:

* `add(a: int, b: int) -> int` — the same shape as 01-04's gate, so a failure here stays
  separable from a model problem.
* `room_status(room: str) -> RoomStatus` — returns a **Pydantic model**, which is what makes
  FastMCP populate `CallToolResult.structuredContent`.

That second tool is not decoration. SPIKE-06 asks whether *structured* results survive a
framework's tracing layer. A probe whose tools returned only strings would send no
structured content at all, and a "not visible" answer would be about the probe. Verified
against the raw `mcp` client before either adapter touched it:

```
structuredContent: {'room': 'kitchen', 'temperature_c': 21.5,
                    'humidity_pct': 44, 'devices': ['kettle', 'ceiling-lamp']}
```

Locally authored rather than `npx -y <public-server>` per `T-01-06-EOP`: a stdio MCP server
is a subprocess with the user's full privileges, and nothing about this measurement needs a
third party's code. It touches no file, opens no socket, and reads no environment.

### A shared condition that is neither framework's fault — record it before comparing

The original stream prompt (`"Reply with exactly the words: hello from the port."`) made
`qwen3.5:9b` overthink literal compliance. Ollama's **default `num_ctx` is 4096** while the
model itself declares `262144`, so the reasoning pass regularly exhausted the served context
and the answer was cut off at exactly `4075 + 21 = 4096` tokens.

Measured on both HTTP routes, identical prompt:

| Route | Used by | Trials | `finish_reason: length` |
|---|---|---|---|
| `/api/chat` (native) | LangChain (`langchain-ollama`) | 3 | **1** — at 4075 |
| `/v1/chat/completions` (OpenAI-compatible) | Pydantic AI (`OllamaProvider`) | 4 | **2** — at 4075 |

**Both routes truncate, at the identical ceiling.** This is a daemon + model property, not a
framework property, and the bake-off is not permitted to charge it to either side. The
prompt was changed to `"Say hello."` (285–598 reasoning tokens, 3/3 completed) and both
adapters re-run under the new prompt.

One *genuine* framework difference falls out of it, and it favours Pydantic AI:

> **LangChain returns the truncated answer silently.** Pydantic AI raises
> `UnexpectedModelBehavior: Model token limit (provider default) exceeded before any
> response was generated` and names the remedy. Under the original prompt the LangChain
> adapter would have handed the caller a short or empty string with `done_reason: "length"`
> buried in `response_metadata`; the Pydantic AI adapter refused to pretend. Both adapters
> now record `finish_reason` / truncation counts so this can never again be mistaken for a
> difference in capability.

---

## 1. SPIKE-05 — do Ollama token counts come back non-`None`?

### Answer: **YES on both frameworks**, on the streaming path, read after aggregation.

CLAUDE.md lists *"token counts come back `None` for Ollama"* as a rough edge and part of why
its LangChain recommendation is only MEDIUM confidence. 01-04 refuted it for the
**non-streaming** path. Pitfall 8 says the `None` belongs to the *streaming* path, which
this plan owns.

| | LangChain | Pydantic AI |
|---|---|---|
| Usage after aggregation | `{input 13, output 370, total 383}` | `{input 13, output 254, total 267}` |
| Read from | `on_llm_end` → `usage_metadata` | `run_stream.usage` + `after_model_request` |
| `is_populated` | **true** | **true** |
| Usage records populated in the whole trace | **3 / 3** | **3 / 3** |
| Streamed chunks carrying usage | **1 of 334** | **0 of 4** (none exposed at all) |
| Naive first-chunk read | `null` | `null` |

### The finding underneath the answer

**LangChain: 1 populated chunk out of 334.** That single number is the whole of Pitfall 8,
measured rather than argued — 333 of 334 chunks carry `usage_metadata = None`, so a handler
reading usage off a chunk has a **99.7 % chance of reporting `None`**. Reproduced across two
runs (1/261 and 1/334). The negative control ran on the same live stream:
`naive_first_chunk_read` is `null` while the aggregated read is populated. Same tokens, same
run, two readers, opposite answers. **Reading position, not framework capability, decides
SPIKE-05 on the LangChain side.**

**Pydantic AI cannot make that mistake.** `stream_text(delta=True)` exposes *no* per-delta
usage whatsoever, so there is nothing to misread — the count is available only from
`result.usage` after the stream closes and from the `after_model_request` hook. Zero chances
to get it wrong, versus LangChain's 334. That is a real ergonomic advantage and it is the
kind of thing a line count does not capture.

`UsageAggregator.usage` **raises** `UsageReadTooEarly` if read before the stream closes,
rather than returning the misleading `None`, so on both sides the mistake is unavailable to
make quietly.

> **Both adapters needed a correction on the way here.** `AgentRunResult.usage` and
> `StreamedRunResult.usage` are **properties** in 2.13.0, not the `usage()` *method* every
> v1-era snippet calls. The first Pydantic AI run reported `final_usage: null` purely
> because of that. Pitfall 12's warning generalises past the MCP classes.

> Note on the counts themselves: 254–370 output tokens for a nine-word greeting. `qwen3.5`
> is a *thinking* model; reasoning is counted in `output_tokens` but never appears in the
> streamed text. 01-04 flagged this for SPIKE-08's time-to-first-token; it is visible here too.

---

## 2. SPIKE-06 — are MCP tool args AND structured results visible through callbacks?

### Answer: **YES on both frameworks, with zero cloud.** CLAUDE.md's concern is refuted.

Read from the **tracing layer** (`on_tool_start`/`on_tool_end`; `before_tool_execute`/
`after_tool_execute`), never from the code that drove the round trip — SPIKE-06 is a
question about callbacks, so evidence assembled outside them would answer a different one.

| | LangChain | Pydantic AI |
|---|---|---|
| Tool **args** seen | `{"room": "kitchen"}` | `{"room": "kitchen"}` |
| Args shape | parsed dict via `inputs=` | parsed dict via `args=` |
| Tool **result** type at the hook | `langchain_core.messages.tool.ToolMessage` | `builtins.dict` |
| Structured payload | inside `.artifact['structured_content']` | **is the result** — no wrapper |
| **Matches the server's frozen fixture** | **true** | **true** |
| Naive `str(output)` capture matches fixture | **false** | **false** |

The assertion that carries the requirement is `structured_content_matches(result,
EXPECTED_STRUCTURED)` — a byte-for-byte comparison against what the server is *known* to
have sent, not "an artifact was present". `artifact_present` alone would be satisfied by any
tool returning anything; the fixture comparison fails if one field is dropped, renamed, or
stringified. Three negative controls pin it (`changed-value`, `dropped-field`,
`stringified-list`).

### LangChain: Pitfall 9 confirmed exactly as RESEARCH read it from the wheel

`langchain_mcp_adapters` converts each MCP tool into a `StructuredTool` with
`response_format="content_and_artifact"`, and `on_tool_end` receives a `ToolMessage` whose
`.artifact` is `{'structured_content': {...}}`. Run against the *same live `ToolMessage`*,
Pitfall 9's `str(output)` capture returns `structured_content: null` and
`artifact_present: false`. The payload is not merely unparsed; as data it is gone — the
resulting string does not even contain `21.5`.

> **The structured half is visible, and the difference between "visible" and "invisible" is
> one `str()` call in the handler.** CLAUDE.md's *"LangChain callbacks fail to cleanly
> surface MCP tool call args + results"* is **refuted**, but the failure mode it anticipated
> is real and one line deep.

### Pydantic AI: the trap does not exist — and the instrument nearly said otherwise

`after_tool_execute` hands over the MCP server's `structuredContent` as a **plain `dict`**.
There is no content/artifact split, so there is nothing to drop. Pitfall 9 has no analogue
here.

**This nearly produced a false negative against Pydantic AI, caused by a defect in our own
measuring device.** The first version of the shared `split_tool_output()` helper only
recognised the *wrapped* shapes, so an unwrapped dict came back `artifact_present: false` —
which reads as "the structured half was lost" when the truth was the opposite. Had it been
left, the bake-off would have scored Pydantic AI as failing SPIKE-06 for a reason that had
nothing to do with Pydantic AI. Fixed, pinned by
`test_split_handles_the_unwrapped_dict_pydantic_ai_delivers`, and recorded here rather than
quietly patched, because it is the same defect class as 01-04's vacuous no-cloud assertion
and 01-03's dicta finding: **the instrument was wrong in a direction that looked like a
result.**

### The other way SPIKE-05/06 could have returned a false negative

```
LangChain    start_hooks_that_fired: ["on_chat_model_start"]   ← on_llm_start fired ZERO times
Pydantic AI  start_hooks_that_fired: ["before_model_request"]  ← one hook, no split
```

**On the LangChain side `on_llm_start` never fired once.** Every prompt in every run arrived
through `on_chat_model_start`. RESEARCH's anti-pattern warning is confirmed live: a handler
implementing only `on_llm_start` — the hook most tutorials show — would have recorded
**nothing at all**, and the spike would have reported "prompts are not visible through
callbacks" about a handler that was never called.

The obvious defence against that is vacuous. `AsyncCallbackHandler` supplies all six hooks
as inherited no-ops, so `hasattr(handler, "on_chat_model_start")` is `True` for a handler
that overrides none of them. `port.missing_hooks()` therefore walks the MRO and stops at the
first framework class, counting only hooks the handler defines *itself*. **Presence is not
implementation.**

**Pydantic AI has no equivalent trap.** One `before_model_request` covers every model kind.

### Supplementary

`langchain_mcp_adapters.callbacks` (`LoggingMessageCallback`, `ProgressCallback`,
`ElicitationCallback` with a `CallbackContext(server_name, tool_name)`) is a **different**
mechanism — MCP-protocol callbacks, not LangChain tracing callbacks. It was not needed; the
standard tracing callbacks carry everything the requirement names.

---

## 3. D-17 evidence — side by side

| Measure | LangChain | Pydantic AI | Edge |
|---|---:|---:|---|
| **Port implementation** (code lines, excl. probe) | **245** | **228** | Pydantic AI, by 7 % — a tie |
| Live probe harness (same shape both sides) | 128 | 126 | — |
| Total file (incl. docs) | 542 | 544 | — |
| **Private translation code** | **61** | **61** | **exact tie** |
| **Framework symbols imported** | **4** | **7** | **LangChain** |
| Framework modules touched | 4 | 7 | LangChain |
| **Framework types in a public port signature** | **0** | **0** | tie (both enforced by test) |
| Tracing hooks that must be written | 6 | 5 | — |
| Token events captured by the trace layer | 457 | 483 | tie |
| Usage records populated | 3/3 | 3/3 | tie |
| Chances to misread usage | **334** | **0** | **Pydantic AI** |
| Model load from a named profile | 1 call, `base_url` optional | 2 objects, `base_url` **mandatory** + `/v1` | **LangChain** |
| Ollama transport | first-party `langchain-ollama` | **OpenAI SDK compatibility shim** | **LangChain** |
| Install completeness from 01-04's provisioning | complete | needed `pydantic-ai-slim[openai]` (+5 pkgs) | **LangChain** |
| Tracing hook semantics | observers (fire-and-forget) | **transformers (must `return`)** | **LangChain** (risk) |
| Verify the tracer is actually wired | n/a — passed per call | private `Hooks._registry`, key `_on_event` ≠ `event` | **LangChain** |
| Truncated-answer behaviour | silent | raises and names the cause | **Pydantic AI** |
| Pitfall-9 artifact trap | present | **absent by design** | **Pydantic AI** |
| Dual start-hook trap | present | **absent by design** | **Pydantic AI** |

Measurement is reproducible: `ast`-based, excluding blanks, comments and docstrings, split
at the `# Live probe` boundary. The script is recorded in the 01-06 SUMMARY.

### What LangChain fought us on

1. **The two start hooks.** The highest-cost item, and it is a *documentation* cost, not an
   API one. Nothing in the signatures says chat models bypass `on_llm_start`. Costs ~20
   duplicated lines, and costs the whole measurement if missed.
2. **Usage is late and singular.** 1 chunk in 334.
3. **The artifact half is opt-in by attention.** `on_tool_end(output)` hands over a rich
   object whose interesting half is one attribute deep, with no warning.
4. **`chunk.content` is not a string** on a thinking model — a list of content blocks.
   `_text_of()` (13 lines) exists only to flatten it safely.
5. **`args_schema` is sometimes a dict, sometimes a model.** `langchain-mcp-adapters` 0.3.0
   returns a plain JSON-schema dict where hand-written `StructuredTool`s carry a class.

### What LangChain made easy

1. **`init_chat_model("ollama:qwen3.5:9b")` is literally a string → model factory** — maps
   1:1 onto a YAML profile, in one line, parsing a model id that itself contains a colon.
2. **First-party Ollama provider.** No compatibility shim in the path.
3. **MCP tools are ordinary `StructuredTool`s.** `bind_tools(mcp_tools)` needs no special
   case and the standard callbacks fire for them unchanged.
4. **Passing the whole `tool_call` dict to `tool.ainvoke()`** returns a `ToolMessage` with
   the artifact attached and the id already wired for the follow-up turn.

### What Pydantic AI fought us on

1. **Ollama is not reachable out of the box.** `Agent("ollama:qwen3.5:9b")` raises
   `ImportError: Please install the openai package to use the Ollama provider`. The Ollama
   provider is built on the **OpenAI SDK**; 01-04's `pydantic-ai-slim` install did not
   include the extra. Resolved by `pydantic-ai-slim[openai]==2.13.0` (+5 packages: `openai`
   2.47.0, `jiter`, `regex`, `tiktoken`, `tqdm`). For a local-first, provider-neutral
   project this is a real architectural wrinkle, not merely a packaging one.
2. **`base_url` is mandatory and means something different.** Without it:
   `UserError: Set the OLLAMA_BASE_URL environment variable…`. And it must carry the `/v1`
   sub-path. **The same PAAF `ModelProfile` cannot be handed to both adapters unchanged** —
   a *semantic* leak through a port field that no type checker would catch.
3. **The hooks are transformers, not observers.** Every hook must return the value it was
   given. A tracer that forgets a `return` does not merely fail to record — it corrupts the
   run it was watching. Observation is not side-effect-free.
4. **Confirming your tracer is wired requires private state.** 2.13.0 exposes no public
   accessor; `repr(hooks)` renders `Hooks({'before_model_request': 1})` but there is no
   supported way to ask. And the registry key for `hooks.on.event(...)` is `_on_event`, not
   `event` — two layers of private detail to answer "is my tracing attached?".
5. **`usage` is a property, not a method** (§1). Pitfall 12 generalises well past MCP.
6. **The documented `MCPToolset("server.py")` shortcut lets FastMCP guess an interpreter**,
   which a three-venv spike cannot allow. An explicit `StdioTransport(command, args)` was
   used instead — and it maps 1:1 onto `McpServerSpec`, so this cost nothing.

### What Pydantic AI made easy

1. **One prompt hook.** No chat/completion split, hence no dual-hook trap.
2. **No artifact unwrapping.** Structured MCP content arrives as a dict.
3. **No per-chunk usage to misread.** The Pitfall 8 false negative is unavailable.
4. **`MCPToolset` accepts a transport object directly** and is a plain async context
   manager, so lifecycle is explicit.
5. **It refuses to hand back a truncated answer as if it were complete.**

---

## 4. Privacy — asserted, not assumed (PRIV-02 / T-01-06-TEL)

```
LangChain    {"langsmith_tracing_enabled": false, "real_logfire_installed": false}
Pydantic AI  {"capabilities_attached": ["Hooks"], "instrumentation_enabled": false,
              "real_logfire_installed": false}
```

Both checked at runtime inside the probe, not inferred from environment variables (01-04's
rule). Tracing on both sides is an in-process handler draining into a plain Python list.
No exporter is constructed. `pydantic_ai.capabilities.Instrumentation` — the
OpenTelemetry/Logfire integration point — is **not attached**; only `Hooks` is.

The only network traffic in either run is `127.0.0.1:11434`. The only subprocess is the
local MCP server. **Both frameworks support full in-process observability with zero cloud.**
The `openai` SDK added for the Ollama provider is pointed at loopback and no
`OPENAI_API_KEY` is set (`OllamaProvider` substitutes the placeholder `api-key-not-set`).

---

## 5. SPIKE-07 verdict

### On the question as asked — "which is easier to hide behind a port" — **there is no decisive winner, and saying so is the finding.**

The measurement does not support a confident answer:

* **245 vs 228 code lines** to implement the identical port. A 7 % gap is noise at this scale.
* **61 vs 61 lines** of private translation code — an exact tie, and this is the number that
  most directly answers "what does the boundary cost".
* **0 vs 0** framework types reaching a public signature, both enforced by a test that is
  demonstrably capable of failing.

Where they differ, they differ in *opposite* directions and roughly cancel:

| Axis | Winner | Why it matters to PAAF |
|---|---|---|
| Coupling surface (4 vs 7 imported symbols) | **LangChain** | Fewer symbols to re-pin when the framework moves |
| Provider ergonomics (`init_chat_model` vs Provider+Model+`/v1`) | **LangChain** | Model profiles are a *headline user-facing feature*; a one-line string→model factory maps onto YAML with no adapter logic |
| Local-first transport (native vs OpenAI shim) | **LangChain** | A local-first project routing Ollama through the OpenAI SDK is an odd dependency to own |
| Tracing safety (observer vs transformer) | **LangChain** | A tracing bug that corrupts the run is a worse failure mode than one that loses a record |
| Trap density (dual hooks, chunk usage, artifact) | **Pydantic AI** | Three separate false-negative traps simply do not exist there |
| Error honesty (silent truncation vs raise) | **Pydantic AI** | Silent degradation is the worst property a voice assistant can have |

**What specifically was easier, named as D-19 requires:** *hiding the **model-loading**
half was clearly easier with LangChain* — one string, one call, no provider object, no
mandatory base URL, no compatibility shim, and a `ModelProfile` that could be passed
verbatim. *Hiding the **tracing** half was clearly easier with Pydantic AI* — one prompt
hook instead of two, structured tool results already unwrapped, and no way to read token
usage at the wrong moment. Neither advantage is large enough to carry the decision alone.

### What actually decides it — and it is not what CLAUDE.md predicted

CLAUDE.md rated Decision 1 **MEDIUM** and named one falsifier:

> *"If MCP traces are opaque → switch to Pydantic AI. This is the falsification test for
> Decision 1."*

**That test has now run, and it came back negative. LangChain's MCP traces are not opaque.**
Tool args arrive as a parsed dict and the full structured payload arrives in the artifact —
verified against the server's frozen fixture, with a negative control proving the check can
fail. The specific stated reason to switch does not exist.

So the LangChain recommendation **stands — but not for the reasons CLAUDE.md gave.** It no
longer rests on superior observability (Pydantic AI is, if anything, slightly better there).
It rests on:

1. **The falsifier fired negative.** No stated reason to switch survives.
2. **Coupling surface and provider ergonomics**, which bear directly on the "user owns the
   assistant's mind" model-profile feature.
3. **A native local-first transport** rather than an OpenAI-SDK shim.
4. **Release cadence** (01-04's independent measurement from the release feed):
   `pydantic-ai-slim` shipped **7 minors in 9 days**; `langchain` shipped **8 patches in 43
   days**, still `1.3.x`. This plan felt that directly — 2.13.0 is three minors behind
   current, and RESEARCH's snippets were already stale against it in two places
   (`MCPToolset(path)` interpreter inference, `usage` property vs method).

**Confidence: MEDIUM, unchanged — but the uncertainty has moved.** It is no longer "can
LangChain see MCP traces?" (answered: yes). It is now "is a 4-vs-7 symbol coupling
difference and a provider-transport preference worth more than a lower trap density?" —
a judgement call, not a measurement, and one this spike deliberately does not pretend to
settle. The two `0.x` packages inside the LangChain 1.x tree (`langchain-mcp-adapters`
0.3.0, `langchain-protocol` 0.0.18) remain the strongest open argument against, and
`langchain-mcp-adapters` is the package that made SPIKE-06 pass.

### The cheap hedge this spike proved viable

`port.py` is 400 code lines and imports nothing. Both adapters keep **zero** framework types
out of its public signatures, and a test enforces it. The 61-line translation layer is the
measured price of that guarantee on *either* framework. CLAUDE.md's rule — *"all LangChain
imports confined to `paaf/_engine/`, enforced by a ruff `banned-api` rule that fails CI"* —
is therefore cheap and it works. **If the choice is wrong, it is recoverable for roughly 250
lines.** That, more than the verdict, is the load-bearing result: the decision does not have
to be right the first time.

---

## 6. D-19 guard — what was NOT built

Both adapters were completed; neither was abandoned, so no framework is rejected on absence
of evidence. Deliberately out of scope, and therefore **unmeasured**:

| Not built | Why | Where it belongs |
|---|---|---|
| LangGraph `interrupt()` → the `confirm` permission tier | CLAUDE.md Spike #6; not in this plan's task list | a later plan / Phase 3 |
| Ordered fallback chains (`ModelFallbackMiddleware` vs `FallbackModel`) | a CLAUDE.md Decision-1 axis this plan's D-16 surface does not include | Phase 3 |
| Multi-turn history, retries, structured output, streaming *tool* calls | outside the five-part D-16 surface | Phase 3 |
| `pydantic-ai-slim` **2.16.0** | 01-04 pinned 2.13.0 so a difficulty could not be ambiguous between "the framework is awkward" and "our snippet is stale". Three minors of drift now exist and two staleness bugs were hit *within* 2.13.0 | re-test decision is 01-07's |
| The `wrap_*` hook family and `Instrumentation` | `Instrumentation` is the Logfire/OTel path and is forbidden (PRIV-02) | never |
| `langchain_mcp_adapters.callbacks` (MCP-protocol callbacks) | not needed — the tracing callbacks carried the requirement | — |
| A second MCP server, or any third-party one | `T-01-06-EOP` | — |

**Attribution note required by D-19:** every difficulty recorded against Pydantic AI in §3 is
*API friction from an unfamiliar v2 surface* or a *provisioning gap* — the missing `openai`
extra, the mandatory `/v1` base URL, `usage` as a property, `_on_event` as a registry key.
**None of them is "the framework resists porting."** It does not. It was hidden behind the
same port in 7 % fewer lines and the identical amount of translation code.

---

## 7. Reproduce

```bash
# daemon (does not survive a reboot — 01-04)
nohup /opt/homebrew/bin/ollama serve > /tmp/paaf-ollama/serve.log 2>&1 &

# unit + conformance tests (80 in the bake-off venv, 119 in the base venv)
uv run --python spike/bakeoff/.venv/bin/python pytest spike/bakeoff/ -q
uv run --python spike/.venv/bin/python pytest spike/ -q

# the two live probes; each prints its evidence as JSON
PYTHONPATH=spike spike/bakeoff/.venv/bin/python -m bakeoff.adapter_langchain
PYTHONPATH=spike spike/bakeoff/.venv/bin/python -m bakeoff.adapter_pydantic_ai
```

Wall clock: ~27 s (LangChain) and ~29 s (Pydantic AI) per probe, plus 90 s for the
bake-off test suite.
