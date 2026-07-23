# Phase 1 — Agent-Framework Bake-off: raw results

**Requirements answered:** SPIKE-05 (Ollama token counts), SPIKE-06 (MCP tool args +
structured results through callbacks), SPIKE-07 (which framework is easier to hide behind
a port).

**Method (D-15/D-16):** one PAAF-typed port (`spike/bakeoff/port.py`, stdlib-only)
implemented twice — `adapter_langchain.py` and `adapter_pydantic_ai.py` — over the *same*
five-part surface: load a model from a named profile, stream tokens, one tool-call round
trip, callback-driven tracing, and an MCP server. SPIKE-05 and SPIKE-06 are read out of the
port's trace layer, not measured beside it.

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
| Telemetry | `langsmith.utils.tracing_is_enabled()` → `False`; real `logfire` package **absent**; 9 telemetry env vars unset (01-04) |

### The MCP target — locally authored, on purpose

`spike/bakeoff/mcp_server/server.py`, 35 code lines, two tools:

* `add(a: int, b: int) -> int` — the same shape as 01-04's gate, so a failure here stays
  separable from a model problem.
* `room_status(room: str) -> RoomStatus` — returns a **Pydantic model**, which is what makes
  FastMCP populate `CallToolResult.structuredContent`.

That second tool is not decoration. SPIKE-06 asks whether *structured* results survive a
framework's tracing layer. A probe whose tools returned only strings would send no
structured content at all, and a "not visible" answer would be about the probe. Verified
directly against the raw `mcp` client before either adapter touched it:

```
structuredContent: {'room': 'kitchen', 'temperature_c': 21.5,
                    'humidity_pct': 44, 'devices': ['kettle', 'ceiling-lamp']}
```

Locally authored rather than `npx -y <public-server>` per `T-01-06-EOP`: a stdio MCP server
is a subprocess with the user's full privileges, and nothing about this measurement needs a
third party's code. It touches no file, opens no socket, and reads no environment.

---

## 1. SPIKE-05 — do Ollama token counts come back non-`None`?

### Answer: **YES — on the streaming path, read after aggregation.**

CLAUDE.md lists *"token counts come back `None` for Ollama"* as a rough edge and part of why
its LangChain recommendation is only MEDIUM confidence. 01-04 already refuted it for the
**non-streaming** path. Pitfall 8 says the `None` belongs to the *streaming* path, which is
what this plan owns. Live, through the port:

```json
"stream": { "yielded_chunks": 5, "chunk_usages_total": 261, "chunk_usages_populated": 1 },
"spike_05": {
  "streaming_usage_after_aggregation": {
    "input_tokens": 21, "output_tokens": 305, "total_tokens": 326,
    "source": "on_llm_end", "is_populated": true },
  "on_llm_end_raw_usage_metadata": { "input_tokens": 21, "output_tokens": 305, "total_tokens": 326 },
  "naive_first_chunk_read": null
}
```

**`1` populated chunk out of `261`.** That single number is the whole of Pitfall 8, measured
rather than argued: 260 of 261 streamed chunks carry `usage_metadata = None`, and a handler
that reads usage from a chunk has a **99.6 % chance of reporting `None`** — a false negative
that would have overturned Decision 1 on a measurement error.

The negative control ran on the same live stream: `naive_first_chunk_read` is `null` while
`streaming_usage_after_aggregation` is populated. Same tokens, same run, two readers, two
opposite answers. Reading position — not framework capability — is what decides SPIKE-05.

`UsageAggregator.usage` **raises** `UsageReadTooEarly` if read before the stream closes,
rather than returning the misleading `None`. The mistake is therefore not available to make
quietly.

`langchain-ollama` 1.1.0 maps Ollama's `prompt_eval_count`/`eval_count` into
`usage_metadata` exactly as RESEARCH read from the wheel. **The rough edge CLAUDE.md cites
is not present in this stack** — but a naive implementation would have manufactured it.

> Note on the token counts themselves: 305 output tokens for a 5-chunk, 20-character reply.
> `qwen3.5` is a *thinking* model; the reasoning pass is counted in `output_tokens` but does
> not appear in the streamed text. 01-04 already flagged this for SPIKE-08's
> time-to-first-token, and it is visible here too.

---

## 2. SPIKE-06 — are MCP tool args AND structured results visible through callbacks?

### Answer: **YES — both halves, with zero cloud.**

Read from the **callback layer** (`on_tool_start` / `on_tool_end`), not from the code that
drove the round trip — SPIKE-06 is a question about callbacks, so evidence assembled outside
them would not answer it:

```json
"spike_06_via_callbacks": {
  "tool_start_args": [ { "room": "kitchen" } ],
  "tool_end_output_types": [ "langchain_core.messages.tool.ToolMessage" ],
  "correct_capture_structured_content": [
    { "room": "kitchen", "temperature_c": 21.5, "humidity_pct": 44,
      "devices": ["kettle", "ceiling-lamp"] } ],
  "naive_capture_structured_content": [ null ],
  "naive_capture_artifact_present": [ false ]
}
```

| Half of the requirement | Hook | Result |
|---|---|---|
| tool **args** | `on_tool_start(inputs=…)` | `{"room": "kitchen"}` — parsed dict, not a rendered string |
| tool **results** (text) | `on_tool_end(output=…)` | present |
| tool **results** (structured) | `on_tool_end(output.artifact)` | **full payload, every field** |

Pitfall 9 is confirmed *exactly* as RESEARCH read it from the wheel:
`langchain_mcp_adapters` converts each MCP tool into a `StructuredTool` with
`response_format="content_and_artifact"`, and `on_tool_end` receives a
`langchain_core.messages.tool.ToolMessage` whose `.artifact` is
`{'structured_content': {...}}`.

**The negative control, on the same live `ToolMessage` object:** `naive_tool_output()` —
Pitfall 9's `str(output)` — returns `structured_content: null` and
`artifact_present: false`. The structured payload is not merely unparsed; as data it is
gone. Its `content` string does not even contain `21.5`.

So the honest form of the SPIKE-06 answer is:

> **The structured half is visible, and the difference between "visible" and "invisible" is
> one `str()` call in the handler.** CLAUDE.md's concern — *"LangChain callbacks fail to
> cleanly surface MCP tool call args + results"* — is **refuted**, but the failure mode it
> anticipated is real and one line deep.

Supplementary: `langchain_mcp_adapters.callbacks` (`LoggingMessageCallback`,
`ProgressCallback`, `ElicitationCallback` with a `CallbackContext(server_name, tool_name)`)
is a **different** mechanism — MCP-protocol callbacks, not LangChain tracing callbacks. It
was not needed; the standard tracing callbacks carry everything the requirement names.

### The other way SPIKE-05/06 could have returned a false negative

```json
"start_hooks_that_fired": ["on_chat_model_start"],
"trace_summary": { "prompts": 3, "prompt_hooks": ["on_chat_model_start"], "tokens": 340,
                   "usage_records": 3, "usage_records_populated": 3,
                   "tool_invocations": 1, "tool_results": 1,
                   "tool_results_with_artifact": 1 }
```

**`on_llm_start` fired zero times across the whole run.** Every prompt arrived through
`on_chat_model_start`. RESEARCH's anti-pattern warning is confirmed live: a handler
implementing only `on_llm_start` — the hook every tutorial shows — would have recorded
**nothing at all**, and the spike would have reported "prompts are not visible through
callbacks" about a handler that was never called.

Worse, the obvious defence is vacuous. `AsyncCallbackHandler` supplies all six hooks as
inherited no-ops, so `hasattr(handler, "on_chat_model_start")` is `True` for a handler that
overrides none of them. `port.missing_hooks()` therefore walks the MRO and stops at the
first framework class, counting only hooks the handler defines *itself*. This is the same
defect class as 01-04's vacuous no-cloud assertion: **presence is not implementation.**

### Privacy (PRIV-02 / T-01-06-TEL)

`{"langsmith_tracing_enabled": false, "real_logfire_installed": false}` — asserted at
runtime inside the probe, not inferred from env vars. Tracing is an in-process
`AsyncCallbackHandler` draining into a plain Python list. No exporter is constructed, no
`Instrumentation` capability is enabled, nothing leaves the process. The only network
traffic in the entire run is `127.0.0.1:11434`, and the only subprocess is the local MCP
server.

---

## 3. D-17 evidence — LangChain side

| Measure | Value |
|---|---|
| **Port implementation** (adapter, excluding the live probe harness) | **232 code lines** |
| Live probe harness (same shape both sides; not a differentiator) | 116 code lines |
| Total file | 501 lines incl. docs · 348 code lines |
| **Framework symbols imported** | **4** — `init_chat_model`, `AsyncCallbackHandler`, `HumanMessage`, `MultiServerMCPClient` |
| Framework modules touched | 4 — `langchain.chat_models`, `langchain_core.callbacks`, `langchain_core.messages`, `langchain_mcp_adapters.client` |
| **Framework types reaching a public port signature** | **0** (enforced by `test_no_framework_type_reaches_the_port_boundary`) |
| Private translation code needed to keep it 0 | **61 code lines** across 6 helpers |

Measurement is reproducible — `ast`-based, excluding blanks, comments and docstrings; the
script is inlined in the SUMMARY's method note.

### What LangChain fought us on

1. **The two start hooks.** The single highest-cost item, and it is a *documentation* cost,
   not an API one. Nothing in the type signatures tells you that chat models bypass
   `on_llm_start`. Costs 20 lines (a duplicated hook) and would cost the whole measurement
   if missed.
2. **Usage is late and singular.** 1 chunk in 261. The framework surfaces the number
   faithfully; it simply arrives at the one moment a naive reader is not looking.
3. **The artifact half is opt-in by attention.** `on_tool_end(output)` hands over a rich
   object whose interesting half is one attribute deep. Nothing warns you.
4. **Content is not a string.** `chunk.content` on a thinking model is a list of content
   blocks; `_text_of()` (13 lines) exists solely to flatten it without assuming a shape.
5. **`args_schema` is sometimes a dict and sometimes a model.** `_tool_spec_of()` handles
   both because `langchain-mcp-adapters` 0.3.0 hands back a plain JSON-schema dict where
   hand-written `StructuredTool`s carry a Pydantic class.

### What LangChain made easy

1. **`init_chat_model("ollama:qwen3.5:9b")` is literally a string → model factory.** It maps
   1:1 onto a YAML profile with no adapter logic at all — one line, and it parses a model id
   that itself contains a colon.
2. **First-party Ollama provider.** `langchain-ollama` is a real provider package; no
   OpenAI-compatibility shim in the path.
3. **MCP tools are ordinary `StructuredTool`s.** `bind_tools(mcp_tools)` needs no special
   case, and the standard tracing callbacks fire for them unchanged.
4. **Passing the whole `tool_call` dict to `tool.ainvoke()`** returns a `ToolMessage` with
   the artifact attached and the id already wired for the follow-up turn.

---

## 4. SPIKE-07 verdict

*(written in §6, after the Pydantic AI side)*

---

## 5. Pydantic AI side

*(pending)*

---

## 6. Verdict

*(pending)*
