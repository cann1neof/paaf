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

<!-- filled by Task 2 -->

---

## Task 3 — Tool-call sanity gate

<!-- filled by Task 3 -->
