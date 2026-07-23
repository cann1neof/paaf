# Bake-off Provisioning Record — Phase 1, Plan 01-04

Raw provisioning evidence for the LangChain-vs-Pydantic-AI bake-off half of the spike
(SPIKE-05/06/07/08). Companion to `raw/voice-provision.md`, which covers the voice half.

**Machine:** Apple M3 Pro, 18 GB unified memory, macOS 26.5.2, arm64.
**Date:** 2026-07-23.
**Survives `rm -rf spike/`** (D-07) — this file lives under `.planning/`, the venv and harness do not.

---

## Task 1 — Ollama daemon, model selection, and the telemetry-off assertion

### 1.1 Telemetry env audit — taken BEFORE any framework or model process started

PRIV-02 and threat `T-01-04-TEL` require that no LangSmith / Logfire / OTLP exporter can
fire. This was **asserted, not assumed**. Audit run at `2026-07-23T11:13Z`, before
`brew install ollama`:

| Variable | State |
|---|---|
| `LOGFIRE_TOKEN` | **UNSET** |
| `LANGSMITH_TRACING` | **UNSET** |
| `LANGSMITH_API_KEY` | **UNSET** |
| `LANGCHAIN_TRACING_V2` | **UNSET** |
| `LANGCHAIN_API_KEY` | **UNSET** (added — the pre-1.0 name still honoured by langsmith-sdk) |
| `LANGSMITH_ENDPOINT` | **UNSET** (added) |
| `LANGSMITH_PROJECT` | **UNSET** (added) |
| `LOGFIRE_SEND_TO_LOGFIRE` | **UNSET** (added) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | **UNSET** (added — pydantic-ai's egress path is OTel, not a Logfire-branded var) |

A whole-environment sweep corroborates the per-variable check:

```
$ env | grep -iE 'langsmith|langchain|logfire|otel|opentelemetry|anthropic_api|openai_api'
(no telemetry/cloud env vars present in the runner environment)
```

The four variables the plan names are the necessary set; the five extra rows were added
because the named four are **not sufficient** — see Deviation 1 in the SUMMARY.

The Ollama daemon itself was additionally launched under
`env -u LOGFIRE_TOKEN -u LANGSMITH_TRACING -u LANGSMITH_API_KEY -u LANGCHAIN_TRACING_V2`,
so the assertion holds for the serving process too, not only for the client.

### 1.2 Ollama install and daemon

| Item | Value |
|---|---|
| Install method | `brew install ollama` (Homebrew 6.0.1) |
| **Ollama version** | **0.32.1** (`ollama version is 0.32.1`) |
| Binary | `/opt/homebrew/bin/ollama` → `/opt/homebrew/Cellar/ollama/0.32.1` |
| New brew deps pulled | `zstd 1.5.7_1`, `python@3.14 3.14.6`, `mlx 0.32.0`, `mlx-c 0.6.0_3` |
| Daemon command | `nohup ollama serve` (detached, log at `/tmp/paaf-ollama/serve.log`) |
| Endpoint | `http://127.0.0.1:11434` — loopback only |
| Health check | `curl -sf http://127.0.0.1:11434/api/tags` → `200`, `{"models":[...]}` |

**Deliberately NOT used:** `brew services start ollama`. That installs a launchd agent that
would survive `rm -rf spike/` and keep starting at login — a Phase-1 artifact outside the
quarantine, weakening 01-01's SC#5 one-`ls` property. A detached `ollama serve` is the
disposable equivalent.

**Deliberately NOT used:** Homebrew's suggested `OLLAMA_FLASH_ATTENTION=1
OLLAMA_KV_CACHE_TYPE="q8_0"`. This is a measurement phase; SPIKE-08's latency numbers must
describe **stock Ollama**, not a tuned build, or the figure cannot be compared to anything
a user would get. The daemon runs with defaults.

**To restart the daemon** (it does not survive a reboot, by design):

```bash
nohup /opt/homebrew/bin/ollama serve > /tmp/paaf-ollama/serve.log 2>&1 &
curl -sf http://127.0.0.1:11434/api/tags   # expect 200
```

### 1.3 Model selection — re-checked at implementation time, as instructed

CLAUDE.md §Decision 6 marks the current community default `[UNVERIFIED — MEDIUM]` and
instructs: *"Re-check `r/LocalLLaMA` at implementation time and benchmark tool-call
reliability yourself — do not take the roadmap's word or mine."* RESEARCH §Open Questions #1
carries the same instruction. That re-check was performed on 2026-07-23 and **it changed the
answer**.

**What the library actually shows today** (`ollama.com/search?c=tools`, popular order, live
2026-07-23):

```
 1. laguna-xs-2.1     2. laguna-s-2.1     3. gemma4      4. qwen3.5     5. qwen3.6
 6. glm-ocr           7. glm-5.1          8. minimax-m2.7  9. nemotron-3-super
10. minimax-m2.5     11. glm-5.2        12. nemotron3   13. minimax-m3  14. lfm2 …
```

**Plain `qwen3` — the tag CLAUDE.md's research example names (`init_chat_model("ollama:qwen3")`)
— does not appear in the top 20 tool-capable models at all.** The Qwen3 *family* recommendation
survives the re-check; the specific tag does not. This is precisely the staleness CLAUDE.md
warned about.

**Why not `qwen3.6` (the newest Qwen release):** its size ladder starts at **27b / 17 GB**.
On an 18 GB unified-memory machine that leaves no headroom at all, and SPIKE-08 needs the LLM
co-resident with Whisper large-v3 (~3 GB) and Chatterbox (~3.2 GB). Disqualified on memory,
not on quality — a clean, hardware-grounded exclusion.

**Why `qwen3.5`:** it is the highest-ranked tool-capable model that (a) is in the Qwen3 family
that CLAUDE.md's standing recommendation names, (b) declares the `tools` capability, (c) offers a
size ladder — 0.8b / 2b / 4b / 9b / 27b / 35b / 122b — that spans both the capability and the
latency need on 18 GB, and (d) is **Apache-2.0**. Point (d) is not incidental: 01-03 discovered
that `dicta-onnx` sits on the Hebrew critical path with **no license declared at all** (L1), so
license hygiene on a critical-path artifact is now a live concern in this phase, not a
theoretical one.

**Selection criterion applied:** tool-calling capability and memory fit — **not chat quality**.
Nothing in this record rests on how well either model writes. Task 3 is the actual benchmark.

### 1.4 Pulled models — exact ids, tags, digests

Both pulls were **explicit and announced** (`T-01-04-DL`), to the local daemon. No cloud
inference. Total 8.7 GB on disk under `~/.ollama/models`; 246 GB free after.

| Role | Tag (pin this, never `latest`) | Digest | Params | Quant | On-disk | Ctx | Pull time |
|---|---|---|---|---|---|---|---|
| **Capability** — SPIKE-05/06/07 | **`qwen3.5:9b`** | `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` | 9.7 B | Q4_K_M | 6,594,474,711 B (6.6 GB) | 262,144 | 73 s |
| **Latency** — SPIKE-08 | **`qwen3.5:2b`** | `324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df` | 2.3 B | Q8_0 | 2,741,192,820 B (2.7 GB) | 262,144 | 32 s |

Declared capabilities, from `GET /api/tags` — **identical for both**:
`["vision", "completion", "tools", "thinking"]`. Architecture `qwen35`. License Apache-2.0
on both. `requires` Ollama ≥ 0.17.1 (have 0.32.1).

**Two models, per RESEARCH Open Q1** ("Consider a smaller model for SPIKE-08's latency shape
than for SPIKE-05/06/07's capability"). `qwen3.5:9b` for the framework bake-off, where a
weak tool-caller would sink SPIKE-06 for reasons unrelated to the framework (A5).
`qwen3.5:2b` for SPIKE-08, where the LLM must sit in memory alongside Whisper and Chatterbox:
2.7 + ~3 + ~3.2 ≈ 8.9 GB, comfortably inside 18 GB. Both are gated in Task 3 — the small one
is not exempt, because an unmeasured latency model could contribute a tool-call failure to
SPIKE-08 that gets misread as a pipeline problem.

**`latest` is deliberately not used anywhere.** `qwen3.5:latest` resolves to the 9b build
today (same digest `6488c96f…`), but a tag that can move is not reproducible, and D-07
promises Phase 7 can re-run this. Pin the explicit tag.

### 1.5 ⚠️ Cloud-routed tags exist in this family — do not pull them

The `qwen3.5` family publishes `qwen3.5:cloud` and `qwen3.5:397b-cloud`, and the model page
lists `cloud` among the family's capabilities. **These route inference to Ollama's hosted
service**, which would silently break the project's no-mandatory-cloud promise (PRIV-02)
while looking exactly like a local model call.

The two tags pulled here carry **no `cloud` capability** — `GET /api/tags` reports
`["vision","completion","tools","thinking"]` for both, and the absence of `cloud` is the
machine-checkable assertion. Any later plan that changes the model must re-check this. A
regression test for it lives in `spike/bakeoff/test_tool_call_sanity.py`.

### 1.6 Notes carried forward for SPIKE-05/06/07/08

1. **Both models are `thinking` models.** They can emit a reasoning pass before the tool
   call. Two consequences: SPIKE-08's time-to-first-token will include think tokens unless
   thinking is disabled, and any tool-call trace must not mistake the reasoning stream for a
   malformed call. Measured behaviour in §3.
2. **Ollama's shipped defaults for this family are `temperature 1`, `top_p 0.95`, `top_k 20`,
   `presence_penalty 1.5`.** Temperature 1 is high for tool-call determinism. The Task 3 gate
   runs at the **stock defaults** on purpose — the question is what a user gets, not what a
   tuned harness can be coaxed into.
3. **262,144-token context on both.** No context-window pressure in any Phase 1 spike.
4. **`ollama` python client is pinned in the bake-off venv** (§2) so §Pitfall 8 can be checked
   against the raw provider before any framework is blamed for `None` token counts.

---

## Task 2 — Bake-off venv

### 2.1 The venv

| Property | Value |
|---|---|
| Path | `spike/bakeoff/.venv` |
| Interpreter | **CPython 3.12.13**, arm64 (uv-managed, same build as `spike/.venv` and `spike/voice/.venv`) |
| Created with | `uv venv --python 3.12 spike/bakeoff/.venv` |
| `sys.prefix` | `/Users/…/paaf/spike/bakeoff/.venv` |
| Git status | **ignored** — `git check-ignore` → `.gitignore:11:spike/**/.venv/`; `git status --porcelain -- spike/` is empty |
| Total packages | 92 |

### 2.2 Separation from the voice venv — proven in both directions

RESEARCH mandates a SEPARATE venv because `chatterbox-tts` hard-pins `torch==2.6.0`,
`transformers==5.2.0`, `diffusers==0.29.0`, `numpy<2.0.0`; resolving those against the
LangChain / Pydantic-AI trees is a resolver fight with no upside. Asserted rather than
assumed — the check runs each interpreter and asks it what it has:

| Interpreter | `torch` | `chatterbox-tts` | `dicta-onnx` | `langchain` | `pydantic-ai-slim` |
|---|---|---|---|---|---|
| `spike/voice/.venv` | 2.6.0 | 0.1.7 | 1.0.9 | **absent** ✅ | **absent** ✅ |
| `spike/bakeoff/.venv` | **absent** ✅ | **absent** ✅ | **absent** ✅ | 1.3.14 | 2.13.0 |

Neither half can import the other. Three venvs now exist under `spike/`, all git-ignored:
`spike/.venv` (base, stdlib-only suite), `spike/voice/.venv` (01-03), `spike/bakeoff/.venv` (this plan).

### 2.3 Requested vs resolved — the pins that moved

| Package | Requested (RESEARCH, verified 2026-07-20) | Resolved 2026-07-23 | Drift |
|---|---|---|---|
| `langchain` | 1.3.14 | **1.3.14** | none — still latest |
| `langgraph` | 1.2.9 | **1.2.9** | none — still latest |
| `langchain-ollama` | 1.1.0 | **1.1.0** | none — still latest |
| `langchain-mcp-adapters` | 0.3.0 | **0.3.0** | none — still latest |
| `pydantic-ai-slim[mcp]` | 2.13.0 | **2.13.0** (pin held) | ⚠️ **latest is now 2.16.0** — see §2.4 |
| `ollama` | ~0.6.2 | **0.6.2** | none — still latest |
| `langchain-core` | 1.4.9 *(transitive; RESEARCH read this wheel)* | **1.5.0** | ⚠️ minor bump — see §2.5 |
| `pytest` / `pytest-asyncio` | 9.1.1 / 1.4.0 | **9.1.1 / 1.4.0** | none |

Every requested version was confirmed present on PyPI and **not yanked** before installing.

### 2.4 ⚠️ Finding: `pydantic-ai` shipped 3 minors in the 3 days since RESEARCH

The plan anticipated this (*"pydantic-ai ships fast minors"*). The re-check quantifies it,
and the number is itself evidence for the bake-off's stability axis:

| `pydantic-ai-slim` | | `langchain` | |
|---|---|---|---|
| 2.10.0 | 2026-07-15 | 1.3.7 | 2026-06-10 |
| 2.11.0 | 2026-07-16 | 1.3.8 | 2026-06-12 |
| 2.12.0 | 2026-07-17 | 1.3.9 | 2026-06-12 |
| **2.13.0** ← RESEARCH pin | 2026-07-18 | 1.3.10 | 2026-06-18 |
| 2.14.0 | 2026-07-21 | 1.3.11 | 2026-06-22 |
| 2.14.1 | 2026-07-21 | 1.3.12 | 2026-07-08 |
| 2.15.0 | 2026-07-22 | 1.3.13 | 2026-07-10 |
| **2.16.0** ← latest today | 2026-07-23 | **1.3.14** ← latest today | 2026-07-16 |

**7 MINOR releases in 9 days** for pydantic-ai, versus **8 PATCH releases in 43 days** for
LangChain, which has not left `1.3.x`. CLAUDE.md scores "API stability history" as a
decision axis and records that pydantic-ai shortened its own no-breaking-change window from
six months to three; this cadence is the same fact observed from the release feed rather than
from the vendor's blog post. **Carry it into 01-10's DECISIONS.md** — it was obtained free,
as a side effect of re-verifying a pin.

**2.13.0 was installed, not 2.16.0**, deliberately: RESEARCH established the v2 MCP surface
(`MCPToolset`, `MCPToolsetClient`, `_build_transport`, the capabilities primitive) by reading
the **2.13.0 wheel source directly**. Installing 2.16.0 would mean SPIKE-07 runs against a
surface nobody has verified, and any failure would be ambiguous between "the framework is
awkward" and "our snippet is three minors stale". A measurement phase should measure the
artifact it has read. 01-07 owns the judgement of whether the drift needs re-testing.

### 2.5 ⚠️ `langchain-core` resolved to 1.5.0, not the 1.4.9 RESEARCH read — re-verified

`langchain==1.3.14` does not pin `langchain-core` exactly, so it resolved forward to **1.5.0**
(released 2026-07-21). RESEARCH's central SPIKE-05/06 finding — *"CHAT models fire
`on_chat_model_start`, NOT `on_llm_start`; implement BOTH"* — was read from the **1.4.9**
wheel. Silently accepting a different wheel would make that finding unverified at exactly the
point SPIKE-05 depends on it. Re-checked against the installed 1.5.0:

| Hook on `AsyncCallbackHandler` | Present in 1.5.0? | Signature matches RESEARCH? |
|---|---|---|
| `on_chat_model_start(serialized, messages, *, run_id, parent_run_id, tags, metadata, …)` | ✅ | ✅ |
| `on_llm_start(serialized, prompts, *, run_id, parent_run_id, …)` | ✅ | ✅ |
| `on_llm_new_token(token, *, chunk, run_id, …)` | ✅ | ✅ |
| `on_llm_end(response, *, run_id, …)` | ✅ | ✅ |
| `on_tool_start(serialized, input_str, *, run_id, inputs, …)` | ✅ | ✅ |
| `on_tool_end(output, *, run_id, …)` | ✅ | ✅ |

**All six survive the bump with the recorded signatures.** RESEARCH's §Code Examples
`SpikeTrace` handler is valid against the installed tree. SPIKE-05/06 may proceed on it.

### 2.6 ⚠️ Both telemetry exporters are physically present in the venv — and are inert

An env-var audit alone would have missed this. `langchain` pulls **`langsmith==0.10.10`** and
`pydantic-ai-slim` pulls **`logfire-api==4.38.0`** and **`opentelemetry-api==1.44.0`** as hard
transitive dependencies. They are in the venv whether or not anyone wants them. PRIV-02 is
about *egress*, not about absence, so the assertion has to be runtime state:

| Check | Result |
|---|---|
| `langsmith.utils.tracing_is_enabled()` | **`False`** — no run tree is exported |
| real `logfire` package installed? | **No** — only `logfire-api`, which is upstream's documented **no-op shim** when `logfire` is absent |
| `langchain_core.globals.get_debug()` / `get_verbose()` | `False` / `False` |
| `LANGSMITH_TRACING` / `LANGCHAIN_TRACING_V2` in `os.environ` | absent / absent |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset — `opentelemetry-api` has no exporter configured |

`T-01-04-TEL` is mitigated in the venv as well as in the shell. The standing rule for
01-05/06/07: **do not `pip install logfire`, and do not call `Agent(..., instrument=True)` /
`logfire.configure()`.** Installing the real `logfire` package would convert a no-op shim into
a live exporter without any env var changing.

### 2.7 Full resolved freeze (92 packages)

`uv pip freeze --python spike/bakeoff/.venv/bin/python`, 2026-07-23:

```
aiofile==3.11.1
annotated-types==0.7.0
anyio==4.14.2
attrs==26.1.0
authlib==1.7.2
beartype==0.22.9
cachetools==7.1.5
caio==0.9.25
certifi==2026.7.22
cffi==2.1.0
charset-normalizer==3.4.9
click==8.4.2
cryptography==49.0.0
distro==1.9.0
dnspython==2.8.0
email-validator==2.3.0
exceptiongroup==1.3.1
fastmcp-slim==3.4.4
genai-prices==0.0.72
griffelib==2.1.0
h11==0.16.0
httpcore==1.0.9
httpcore2==2.7.0
httpx==0.28.1
httpx-sse==0.4.3
httpx2==2.7.0
idna==3.18
iniconfig==2.3.0
jaraco-classes==3.4.0
jaraco-context==6.1.2
jaraco-functools==4.6.0
joserfc==1.7.4
jsonpatch==1.33
jsonpointer==3.1.1
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
keyring==25.7.0
langchain==1.3.14
langchain-core==1.5.0
langchain-mcp-adapters==0.3.0
langchain-ollama==1.1.0
langchain-protocol==0.0.18
langgraph==1.2.9
langgraph-checkpoint==4.1.1
langgraph-prebuilt==1.1.0
langgraph-sdk==0.4.2
langsmith==0.10.10
logfire-api==4.38.0
markdown-it-py==4.2.0
mcp==1.28.1
mdurl==0.1.2
more-itertools==11.1.0
ollama==0.6.2
opentelemetry-api==1.44.0
orjson==3.11.9
ormsgpack==1.12.2
packaging==26.2
platformdirs==4.11.0
pluggy==1.6.0
py-key-value-aio==0.4.5
pycparser==3.0
pydantic==2.13.4
pydantic-ai-slim==2.13.0
pydantic-core==2.46.4
pydantic-graph==2.13.0
pydantic-settings==2.14.2
pygments==2.20.0
pyjwt==2.13.0
pytest==9.1.1
pytest-asyncio==1.4.0
python-dotenv==1.2.2
python-multipart==0.0.32
pyyaml==6.0.3
referencing==0.37.0
requests==2.34.2
requests-toolbelt==1.0.0
rich==15.0.0
rpds-py==2026.6.3
sniffio==1.3.1
sse-starlette==3.4.6
starlette==1.3.1
tenacity==9.1.4
truststore==0.10.4
typing-extensions==4.16.0
typing-inspection==0.4.2
urllib3==2.7.0
uuid-utils==0.17.0
uvicorn==0.51.0
websockets==15.0.1
xxhash==3.8.1
zstandard==0.25.0
```

Notable transitives for later plans: **`mcp==1.28.1`** and **`fastmcp-slim==3.4.4`** (SPIKE-06
runs both adapters against the same MCP protocol version — a fair comparison);
**`pydantic==2.13.4`**, matching CLAUDE.md's stack pin exactly; **`langchain-protocol==0.0.18`**,
a `0.0.x` package now inside the LangChain 1.x dependency tree, which is worth noting next to
`langchain-mcp-adapters==0.3.0` when 01-10 weighs the "LangChain is the stable one" claim.

### 2.8 Import smoke — every entry point the bake-off needs

All eight pass under `spike/bakeoff/.venv/bin/python`:

```
OK  from langchain.chat_models import init_chat_model
OK  from langgraph.graph import StateGraph
OK  from langchain_ollama import ChatOllama
OK  from langchain_core.callbacks import AsyncCallbackHandler
OK  from langchain_mcp_adapters.client import MultiServerMCPClient
OK  from pydantic_ai import Agent
OK  from pydantic_ai.mcp import MCPToolset          # v2 surface; MCPServerStdio is GONE
OK  import ollama
```

---

## Task 3 — Tool-call sanity gate

### 3.1 VERDICT: **GREEN — no model swap required**

`qwen3.5:9b` and `qwen3.5:2b` emitted a **well-formed tool call on 30 of 30 trials, 100%
in every condition**. Assumption **A5 is confirmed**: the instrument works, so a weak
tool-caller cannot be the hidden cause of a SPIKE-06 MCP-tracing failure. SPIKE-06 and
SPIKE-07 may proceed, and their verdict will be about the frameworks.

Report from `SPIKE_TOOL_TRIALS=5 python spike/bakeoff/tool_call_sanity.py`:

```
host=http://127.0.0.1:11434  trials=5  min_reliability=1.0

=== qwen3.5:9b  caps=['completion', 'vision', 'tools', 'thinking'] ===
  [PASS] raw       add       100% (5/5)  mean   5.3s  usage={'prompt_eval_count': 364, 'eval_count': 110}
  [PASS] raw       get_time  100% (5/5)  mean   3.8s  usage={'prompt_eval_count': 356, 'eval_count': 76}
  [PASS] langchain add       100% (5/5)  mean   5.2s  usage={'input_tokens': 346, 'output_tokens': 115, 'total_tokens': 461}
  [PASS] langchain get_time  100% (5/5)  mean   3.5s  usage={'input_tokens': 338, 'output_tokens': 76, 'total_tokens': 414}

=== qwen3.5:2b  caps=['completion', 'vision', 'tools', 'thinking'] ===
  [PASS] langchain add       100% (5/5)  mean   2.8s  usage={'input_tokens': 346, 'output_tokens': 120, 'total_tokens': 466}
  [PASS] langchain get_time  100% (5/5)  mean   1.8s  usage={'input_tokens': 338, 'output_tokens': 88, 'total_tokens': 426}

GATE: GREEN
```

Run at **stock sampling defaults** (`temperature 1`, `top_p 0.95`, `top_k 20`,
`presence_penalty 1.5`) — not a tuned harness. The question was what a user gets.

### 3.2 What "well-formed" was actually required to mean

A naive `if response.tool_calls:` would pass on a call with a stringified integer and a
missing operand. `validate_tool_call` checks seven independent conditions:

1. at least one tool call (i.e. not prose) — the most likely failure mode;
2. **exactly** one (both prompts admit exactly one);
3. the name is among the bound tools (catches hallucinated tools);
4. the name is the **expected** one — this measures tool **selection**, not just emission.
   Two cases, one per tool, so a model that always calls `add` scores 50%, which a
   single-case gate would score 100%;
5. arguments are a dict **and** survive a JSON round trip;
6. argument keys match the schema exactly — nothing missing, nothing extra;
7. argument types and **values** match (`{"a": 48271, "b": 9384}`, large arbitrary
   addends so they cannot be a memorised constant). `bool` is explicitly excluded from
   `integer`, because Python's `isinstance(True, int)` is `True` and `{"a": true}` would
   otherwise pass as a valid integer.

### 3.3 The gate is proven capable of failing

01-03's rule — *a gate that cannot fail manufactures confidence* — is enforced by **ten
negative controls**, each a hand-built malformed call the validator must reject, *and
reject for the stated reason*: prose, two calls, hallucinated name, wrong tool, args as a
JSON string, missing required arg, extra arg, stringified integer, bool-as-integer, and
right-shape-wrong-values. Two complementary tests assert a correct call is **accepted**,
since a validator that rejects everything is equally useless.

`validate_tool_call` takes the framework-free shape `[{"name": str, "args": dict}]`, which
is what makes those controls possible without model traffic — and is why they run in
0.12 s while the live gate takes 88 s.

### 3.4 ⚠️ Finding: the no-cloud assertion was silently vacuous, and the gate caught it

The first run of the fast suite **failed**, on this:

```
AssertionError: model 'qwen3.5:9b' does not declare the 'tools' capability: []
```

Cause: the `ollama` python client 0.6.2 models the `/api/tags` response with a pydantic
schema whose `Model` class declares only `model / modified_at / digest / size / details`
— **no `capabilities` field**. The daemon *does* send `capabilities` on `/api/tags`
(confirmed against the raw HTTP endpoint), but pydantic drops the unknown key. So
`client.list()` reports `[]` for every model.

Why that matters beyond a typo: the check written against `list()` was

```python
if "cloud" in caps:   # caps is always [] -> never true
    raise AssertionError(...)
```

**The PRIV-02 no-cloud guarantee would have passed for every tag, including a genuinely
cloud-routed `qwen3.5:cloud`.** A guarantee that is vacuously true is worse than none,
because it reads as evidence. `capabilities_of()` now reads `/api/show` (whose schema
*does* declare `capabilities`) and treats an empty list as an **error**, never as "no
cloud capability". Two regression tests pin it, one of which fails deliberately if a
future `ollama` client adds the field, so the workaround retires itself instead of rotting.

This is the same class of defect as 01-03's dicta finding: it lives in the *interaction*
between two packages' schemas and is invisible to reading either one.

### 3.5 Informational, carried to SPIKE-05 — token counts are NOT `None`

CLAUDE.md §Decision 1 lists *"Token counts come back `None` for Ollama"* as a known rough
edge and a reason the LangChain recommendation is only MEDIUM confidence. RESEARCH
§Pitfall 8 warns against concluding it from a streaming chunk. Measured here on the
**non-streaming** path, at both levels:

| Path | Field | Value |
|---|---|---|
| raw `ollama` client | `prompt_eval_count` / `eval_count` | **364 / 110** — non-`None` |
| `init_chat_model("ollama:…")` | `usage_metadata` | **`{'input_tokens': 346, 'output_tokens': 115, 'total_tokens': 461}`** — non-`None` |

`langchain-ollama` 1.1.0 is correctly mapping `prompt_eval_count`/`eval_count` into
`usage_metadata`, exactly as RESEARCH read from the wheel. **This does not close SPIKE-05**
— the open question is the *streaming* path, which is where Pitfall 8 says the `None`
actually appears, and SPIKE-05 owns it. Recorded so 01-06 starts from a known baseline
rather than rediscovering the non-streaming half. Per 01-03's pattern this check is
informational: the test asserts only that the fields *exist* and prints their values, so a
negative answer would be a finding to carry forward, not a gate failure.

### 3.6 Observed shape for SPIKE-08 (not a measurement — that is 01-09's job)

Both models are **thinking** models and emit a reasoning pass before the tool call, in a
separate `thinking` field rather than mixed into `content` (so a tracer will not mistake
reasoning for a malformed call). Single-turn tool-call wall time, warm, unbatched:

| Model | `add` | `get_time` |
|---|---|---|
| `qwen3.5:9b` | ~5.2 s | ~3.5 s |
| `qwen3.5:2b` | ~2.8 s | ~1.8 s |

Roughly a 2× gap, which is what motivated pulling the smaller tag. These are **not** the
SPIKE-08 numbers — no warmup discipline (Pitfall 10), n=5, and the think tokens are
included. They only confirm the latency model is worth having.

### 3.7 Artifacts and how to run

| File | Role |
|---|---|
| `spike/bakeoff/tool_call_sanity.py` | tools, cases, validator, both probes, env assertions, CLI report |
| `spike/bakeoff/test_tool_call_sanity.py` | 39 tests — 32 fast (env + negative controls), 7 slow (live gate) |
| `spike/bakeoff/conftest.py` | interpreter-keyed collection guard (01-03 pattern) |
| `spike/bakeoff/__init__.py` | stops this dir's conftest shadowing `spike/conftest.py` — see SUMMARY deviation 3 |

```bash
# the gate
uv run --python spike/bakeoff/.venv/bin/python pytest spike/bakeoff/ -q          # 39 passed, 88s
# fast layer only
uv run --python spike/bakeoff/.venv/bin/python pytest spike/bakeoff/ -q -m "not slow"
# standalone report at higher n
SPIKE_TOOL_TRIALS=5 spike/bakeoff/.venv/bin/python spike/bakeoff/tool_call_sanity.py
```

Suite status across all three venvs after this plan: base **61 passed**, voice **70 passed**
(fast), bake-off **39 passed** (full).

### 3.8 Model swaps

**None.** No swap was needed; both pulled tags cleared the gate at 100% on the first
attempt. Had either failed, the plan's remedy — swap the model now and record the reason
here, rather than let SPIKE-06 misattribute the failure to the framework — would have
applied. The assertion message inside `test_capability_model_emits_well_formed_tool_calls`
carries that instruction, so a future re-run that goes red says what to do.
