# Phase 3: paaf-llm Core (single agent) - Pattern Map

**Mapped:** 2026-08-05
**Files analyzed:** 15 new/modified
**Analogs found:** 11 with a real codebase analog / 15 total (4 are NET-NEW seams — noted explicitly)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/paaf-llm/src/paaf_llm/ports.py` | port/interface | streaming (request-response) | `paaf-core/src/paaf_core/secrets/interface.py` (Protocol seam) + `paaf-core/net/endpoint.py` (frozen dataclass types) | **NET-NEW** (structural precedent only) |
| `packages/paaf-llm/src/paaf_llm/agent.py` | service (engine) | streaming + event-driven | `paaf-trace/src/paaf_trace/store.py` (async loop, trace draining) | **NET-NEW** (structural precedent only) |
| `packages/paaf-llm/src/paaf_llm/compose.py` | utility (pure fn) | transform | `paaf-core/config/schema.py` (frozen dataclass discipline) | partial (role-match: pure deterministic module) |
| `packages/paaf-llm/src/paaf_llm/profiles.py` | model (schema) | CRUD (config validate) | `paaf-core/src/paaf_core/config/schema.py` | **exact** |
| `packages/paaf-llm/src/paaf_llm/fake/__init__.py` | test-double (shipped) | streaming | `paaf-trace/src/paaf_trace/_testing/fake_tts.py` | **exact** |
| `packages/paaf-llm/src/paaf_llm/cli.py` | cli/controller | request-response | (no existing CLI in repo) | **NET-NEW** (no analog) |
| `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` | adapter (real) | streaming | marker exists; `secrets/fernet_backend.py` as "impl behind Protocol" | role-match (impl-behind-port) |
| `packages/paaf-llm/src/paaf_llm/__init__.py` | config (re-exports) | — | existing stub `paaf_llm/__init__.py` | **exact** |
| `packages/paaf-llm/pyproject.toml` | config | — | existing `packages/paaf-llm/pyproject.toml` | **exact** |
| `packages/paaf-trace/.../schema.sql` (+`store.py`) | migration/schema | — | `paaf-trace/schema.sql` + `store.py` `RunEvent` | **exact** |
| `packages/paaf-llm/tests/conftest.py` | test fixture | — | (no conftest exists yet) + `fake_tts` fixture usage | **NET-NEW** (thin) |
| `packages/paaf-llm/tests/test_*.py` | test | — | `paaf-core/tests/test_config_schema.py`, `paaf-trace/tests/test_trace_schema.py` | role-match |
| `.importlinter` (modified) | config | — | existing `.importlinter` | **exact** |
| `tests/negcontrol/*` (extend) | test | — | `tests/negcontrol/test_import_boundary.py` | **exact** |
| `.github/workflows/*.yml` (extend) | config/ci | — | `wheel-independence.yml` | **exact** |

---

## Pattern Assignments

### `packages/paaf-llm/src/paaf_llm/profiles.py` (model / schema) — EXACT analog

**Analog:** `packages/paaf-core/src/paaf_core/config/schema.py`

Copy directly: the `extra="forbid"` model_config, the `Field(..., json_schema_extra={"reload_tier": ...})` metadata pattern, and the `ReloadTier` enum import. RESEARCH Pattern 4 says: new profile fields reuse this exact `reload_tier` metadata (`provider` change ≈ RESTART matching the existing `ModelConfig.provider` precedent at lines 52-54; adding a profile ≈ WARM/COLD).

**Schema + forbid pattern** (schema.py lines 44-71):
```python
class ModelConfig(BaseModel):
    # WARM: a new temperature applies on the next turn.
    temperature: float = Field(
        0.7, ge=0.0, le=2.0, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # RESTART: changing the provider re-wires the engine; restart required.
    provider: str = Field(
        "ollama", json_schema_extra={"reload_tier": ReloadTier.RESTART}
    )

class AppConfig(BaseModel):
    model_config = {"extra": "forbid"}
```

**Cross-field `model_validator`** — NEW logic (RESEARCH Pattern 4, lines 324-335 of RESEARCH). No existing `model_validator` in the codebase; write per the research example (`active_profile`/`fallback_chain`/`peers` reference-integrity, reject self-as-peer, reject undeclared targets). This is MODEL-05 (D-07/D-08) and the `test_peer_validation` Wave-0 test targets it. `ReloadTier` enum lives at schema.py lines 16-28 — import it, do not redefine.

**Decision to surface for planner:** the founder's Claude-discretion note allows profiles to live in `paaf-core/schema.py` OR a new `paaf-llm/profiles.py`. RESEARCH structure (line 191) leans toward `paaf-llm/profiles.py` but flags "may live in paaf-core schema instead." If placed in `paaf-core`, it must reuse the exact `AppConfig` tree above.

---

### `packages/paaf-llm/src/paaf_llm/fake/__init__.py` (shipped test-double, streaming) — EXACT analog

**Analog:** `packages/paaf-trace/src/paaf_trace/_testing/fake_tts.py`

This is the canonical PAAF "shipped fake behind a Protocol, driven by injected control, zero framework imports" precedent. Copy its shape exactly: injected-controllable behavior (fake_tts injects a `_Clock` Protocol; FakeAdapter injects scripted tokens/delays/failures), a narrow `Protocol` for the injected dependency, deterministic output, and a module docstring explaining the negative-control it enables.

**Injected-dependency Protocol + deterministic generator** (fake_tts.py lines 30-35, 74-91):
```python
class _Clock(Protocol):
    """The slice of the ``frozen_clock`` fixture FakeTTS depends on."""
    def now(self) -> float: ...
    def advance(self, seconds: float) -> float: ...

class FakeTTS:
    def synthesize(self, text: str = "") -> Iterator[bytes]:
        self.started_at = self._clock.now()
        self._clock.advance(self._delay)
        self.first_audio_at = self._clock.now()
        yield self._CHUNK
        ...
```

**FakeAdapter surface** (RESEARCH lines 461-468 — the target shape):
```python
class FakeAdapter:                        # implements ChatAdapter
    def program(self, profile_name, *, tokens=None, fail=None, first_token_delay_s=0.0): ...
    #   fail ∈ {ConnectionFailed, RequestTimedOut, ServerError, RateLimited} → raise on stream
    #   first_token_delay_s > budget → engine's asyncio.timeout fires SLOW_FIRST_TOKEN
    #   tokens=[...] → deterministic streaming for multi-turn/history tests
```
Critical constraint (fake_tts docstring lesson + SC#1): NO `langchain` import anywhere in `fake/`. It ships in the wheel and must run framework-uninstalled. Note fake_tts lives under `_testing/`; FakeAdapter under `fake/` and is re-exported from `paaf_llm.__init__` (RESEARCH Pitfall 4) since the fake-adapter suite is the primary correctness surface (D-01).

---

### `packages/paaf-llm/src/paaf_llm/ports.py` (port / PAAF types) — NET-NEW, structural precedent

**No direct analog** — the streaming `ChatAdapter` port + PAAF exception hierarchy is net-new. Closest structural precedents, both in `paaf-core`:

1. **Protocol-as-durable-contract** — `secrets/interface.py` lines 18-41 (`@runtime_checkable`, method-only Protocol, docstring stating "the interface is the durable contract"):
```python
@runtime_checkable
class SecretStore(Protocol):
    def set(self, key: str, value: str) -> None: ...
    def get(self, key: str) -> str | None: ...
```

2. **Frozen dataclass value types** — `net/endpoint.py` lines 28-39 (`@dataclass(frozen=True)` for typed network values). PAAF `Message`/`Usage`/`TurnResult` follow this; RESEARCH Pattern 1 (lines 211-243) uses `@dataclass(frozen=True, slots=True)`.

Follow RESEARCH Pattern 1 (lines 199-245) verbatim for the exception hierarchy (`AdapterError` base carrying `FallbackReason`; `ConnectionFailed`/`RequestTimedOut`/`ServerError`/`RateLimited`). ZERO framework imports (enforced by `test_no_leak.py` + import-linter). **Phase-4 seam:** `TurnResult.handoff: HandoffRequest | None = None` (design-only, always None in Phase 3).

---

### `packages/paaf-llm/src/paaf_llm/agent.py` (engine / fallback loop) — NET-NEW, structural precedent

**No direct analog** for the ordered-fallback streaming loop (RESEARCH Pattern 2, lines 250-278 — copy it). Closest structural precedent for the **async lifecycle + trace-draining** half is `paaf-trace/src/paaf_trace/store.py`.

**Trace-draining pattern** — the engine emits `RunEvent`s the same fire-and-forget way the store consumes them (store.py lines 124-135):
```python
def emit(self, event: object) -> None:
    """Hand an event to the writer WITHOUT blocking (hot-path safe)."""
    try:
        self._q.put_nowait(event)
    except asyncio.QueueFull:
        self._dropped += 1
```
Engine calls `trace.emit(RunEvent(...))` post-turn and `trace.emit(FallbackEvent...)` per fallback (D-06). SPIKE-05: read `adapter.last_usage()` AFTER stream aggregation, not per chunk (RESEARCH Pattern 6, anti-pattern line 371).

**Fallback loop core** (RESEARCH Pattern 2, lines 255-276) — `asyncio.timeout(profile.first_token_budget_s)` around only the first `__anext__`; classify `AdapterError.reason`; `await gen.aclose()` on timeout; commit to first profile that yields; `raise AllProvidersFailed(chain)` if all degrade. Do NOT re-fall-back mid-stream (D-04 scope = first token only).

---

### `packages/paaf-llm/src/paaf_llm/compose.py` (pure composer) — partial analog (role-match)

**No behavioral analog.** Follow RESEARCH Pattern 5 (lines 345-361) exactly. Reuse the frozen-dataclass discipline seen throughout `paaf-core` (`@dataclass(frozen=True, slots=True)` for `Segment`). Load-bearing invariant (PERS-05, `test_no_hidden_prompt`): `"\n\n".join(seg.text for seg in segments) == compose(...)` and the composed string contains base + fragments and NOTHING else. One composer feeds both the live path and `paaf prompt`/`--show-prompt` (D-02, no re-derivation).

---

### `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` (real LangChain adapter) — role-match

**Analog for "concrete impl behind a Protocol":** `paaf-core/src/paaf_core/secrets/fernet_backend.py` (the Fernet impl behind `SecretStore`). The marker already exists (see its docstring naming the exact import-linter whitelist edge). Follow RESEARCH Pattern 3 (lines 283-294): `init_chat_model` provider-string mapping, `base_url` from `net/endpoint.py`, `api_key` from `SecretStore.get(profile.api_key_ref)`. Constraints: the ONLY `langchain*` import site; MUST NOT `import httpx` directly (let `langchain-*` own the client so the `no-network-client` contract stays green — RESEARCH Pitfall 3); imported LAZILY (RESEARCH Pitfall 4).

---

### `packages/paaf-llm/src/paaf_llm/cli.py` (thin CLI) — NET-NEW, no analog

**No existing CLI in the repo.** Net-new. click 8.4.2 + rich 15.0.0 (both installed). Keep it thin (D-01) — `chat`, `prompt`, `--show-prompt`, `--provenance`, and the inline `↳ fell back to <profile> (<reason>)` notice (D-06). No logic the library lacks. `[project.scripts] paaf = "paaf_llm.cli:main"` (RESEARCH line 119).

---

### `packages/paaf-trace/.../schema.sql` + `store.py` (additive columns) — EXACT analog

**Analog:** the file itself — `paaf-trace/schema.sql` `runs` table + `store.py` `RunEvent.as_sql()` (lines 37-68).

RESEARCH Pattern 6 / Pitfall 5 recommend option (a): add denormalized `served_by TEXT` + `fallback_trail TEXT` (JSON) columns to `runs`, avoiding a child table (the fire-and-forget `_writer` never returns `lastrowid`, so an FK child table needs writer changes — store.py lines 143-160 confirm no id is surfaced). Extend `RunEvent` (add fields + widen the `INSERT ... VALUES` tuple, mirroring lines 50-68). Add a schema test alongside `paaf-trace/tests/test_trace_schema.py`.

**Existing INSERT shape to widen** (store.py lines 50-68):
```python
def as_sql(self) -> tuple[str, tuple[object, ...]]:
    return (
        ("INSERT INTO runs "
         "(id, prompts, model, started_at, ended_at, "
         "prompt_tokens, completion_tokens, time_to_first_audio) "
         "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"),
        (self.id, self.prompts, self.model, ...),
    )
```

---

### `packages/paaf-llm/pyproject.toml` + `__init__.py` — EXACT analog (modify in place)

Modify the existing files. Add the real `dependencies` (paaf-core, paaf-trace, pydantic, pyyaml, click, rich), the `[project.optional-dependencies] engine = [...]` extra (RESEARCH lines 110-122), and `[project.scripts]`. Keep the existing `[tool.hatch.build.targets.wheel.force-include]` wheel-smoke wiring. `__init__.py` re-exports PAAF types + `FakeAdapter` only — NEVER `_engine` (Pitfall 4).

---

## Shared Patterns

### Adapter-package confinement (langchain behind `_engine`)
**Source:** `.importlinter` `[importlinter:contract:langchain]` + its header comment (lines describing the `ignore_imports = paaf_llm._engine.* -> langchain*` edge).
**Apply to:** `_engine`, `cli.py`, `agent.py`, `ports.py`, `fake/`.
**Modification required (RESEARCH Pitfall 3, Wave-0 gap):** add `langchain_ollama`, `langchain_anthropic`, `langchain_openai` to `forbidden_modules`, then add the `ignore_imports` whitelist for `paaf_llm._engine.* -> langchain*` (and each provider module). Current forbidden list:
```ini
forbidden_modules =
    langchain
    langgraph
    langchain_core
    langchain_mcp_adapters
```

### Negative-control discipline
**Source:** `tests/negcontrol/test_import_boundary.py` (lines 66-99: green-half + red-on-violation pair) and `paaf-llm/tests/test_wheel_smoke.py` (positive + `ModuleNotFoundError` negative control).
**Apply to:** every Wave-0 test. Fallback suite must prove fallback FIRES on each of 4 triggers AND a healthy provider does NOT fall back (`test_healthy_no_fallback`). Add a negcontrol fixture proving a stray `langchain_ollama` import outside `_engine` turns CI red (mirror `paaf_llm_langchain_violation/`).

### Framework-uninstalled wheel job
**Source:** `.github/workflows/wheel-independence.yml` + `scripts/check_wheel_independence.sh` + `paaf-llm/tests/test_wheel_smoke.py`.
**Apply to:** SC#1. Extend the wheel job to `pip install` the wheel WITHOUT `[engine]` and run the full `pytest --pyargs paaf_llm` suite. The existing job already asserts `import paaf_voice`/`paaf_core` raise `ModuleNotFoundError`; add `import langchain` raising `ModuleNotFoundError` while the fake-adapter suite passes green.

### Trace fire-and-forget draining
**Source:** `paaf-trace/store.py` `emit` (lines 124-135) + `RunEvent`/`ToolCallEvent` `as_sql` dataclasses.
**Apply to:** `agent.py`. New event dataclasses expose `as_sql()`; the writer stays event-agnostic (no ORM — CLAUDE.md).

### SPDX header + `from __future__ import annotations`
**Source:** every `.py` file in the repo (e.g. schema.py line 1, endpoint.py lines 1/17).
**Apply to:** all new files — `# SPDX-License-Identifier: Apache-2.0` first line, `from __future__ import annotations`.

---

## No Analog Found

| File | Role | Data Flow | Reason / closest precedent |
|------|------|-----------|----------------------------|
| `paaf_llm/ports.py` | port | streaming | First streaming Protocol + PAAF exception tree in repo. Precedent: `secrets/interface.py` (Protocol shape), `net/endpoint.py` (frozen value types). Follow RESEARCH Pattern 1. |
| `paaf_llm/agent.py` | engine | streaming+event | First agent/fallback loop. Precedent for async lifecycle + trace drain: `paaf-trace/store.py`. Follow RESEARCH Pattern 2. |
| `paaf_llm/cli.py` | cli | request-response | No CLI exists anywhere in the repo. Net-new click/rich surface (D-01/D-02). |
| `paaf_llm/tests/conftest.py` | fixture | — | No conftest exists in any package yet. Model the `FakeAdapter`-programming + async `TraceStore` fixtures on how `fake_tts` is consumed. |

## Metadata

**Analog search scope:** `packages/paaf-core/{config,net,secrets}`, `packages/paaf-trace/{src,tests}`, `packages/paaf-llm`, `tests/negcontrol`, `.github/workflows`, `.importlinter`.
**Files scanned:** ~20 source + config files (all 5 workspace packages enumerated).
**Pattern extraction date:** 2026-08-05
</content>
</invoke>
