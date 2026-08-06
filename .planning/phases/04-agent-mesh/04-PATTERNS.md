# Phase 4: Agent Mesh - Pattern Map

**Mapped:** 2026-08-07
**Files analyzed:** 12 (10 modified, 2 new) + 6 test files
**Analogs found:** 12 / 12 source files (2 new files have role-match analogs only)

Phase 4 is **additive greenfield inside a mature, opinionated package**. Almost every new file has an
exact in-repo analog, and the repo's own docstrings state *why* each pattern exists. The planner
should treat the excerpts below as the house style to copy verbatim, including the
comment-the-rationale convention (every non-obvious line in this codebase carries a `# why` comment
naming the decision ID or threat ID it implements).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `paaf_llm/ports.py` (+ `ToolSpec`, `ToolCall`, `HandoffRequest`, `ToolCallingChatAdapter`, `UndeclaredPeer`) | port / model | transform | itself — `Message`/`Usage`/`ChatAdapter`/`EngineError` | exact (self-precedent) |
| `paaf_llm/profiles.py` (+ `ModelProfile.fallback_chain`/`system_prompt`/`persona`, `LlmConfig.default_agent`/`hop_budget`/observer settings, `_check_refs` additions) | config schema | transform | itself — `peers`/`constraints` fields + `_check_refs` | exact (self-precedent) |
| `paaf_llm/mesh.py` **NEW** — explainer generation, tool-surface construction, peer guard, hop bookkeeping | utility (pure) | transform | `paaf_llm/compose.py` (pure, stdlib-only, deterministic, no I/O) | role-match |
| `paaf_llm/observer.py` **NEW** — supervising-model call, verdict types, capability grant | service | request-response | `paaf_llm/agent.py` `_run_chain` (the only other code that drives an adapter) | role-match |
| `paaf_llm/compose.py` (+ ordered `mesh_fragments` parameter) | utility (pure) | transform | itself — `segments`/`compose` | exact (self-precedent) |
| `paaf_llm/agent.py` (handoff loop wrapping `_run_chain`; awake-state; per-agent chain; drain) | service / engine loop | event-driven (loop) | itself — `turn`/`_run_chain`/`_chain`/`_drain` | exact (self-precedent) |
| `paaf_llm/fake/__init__.py` (+ scripted tool calls, + recorded tool offers, + `stream_with_tools`) | test double | streaming | itself — `program()`/`_Program`/`self.calls` | exact (self-precedent) |
| `paaf_llm/cli.py` (+ `paaf prompt --agent <name>`; render the bound tool surface) | CLI / controller | request-response | itself — `prompt()` command + `--provenance` branch | exact (self-precedent) |
| `paaf_llm/_engine/__init__.py` (+ `bind_tools` translation, `_tool_calls_of`, `last_tool_calls`) | adapter | streaming | itself — `stream` + `_usage_of` + `_translate` | exact (self-precedent) |
| `paaf_llm/__init__.py` (re-export new public PAAF types) | package surface | — | itself — `__all__` block | exact |
| `paaf_trace/schema.sql` (+ `handoffs` table, + `turn_legs` table) | migration / schema | CRUD (append) | itself — `runs`/`tool_calls` `CREATE TABLE IF NOT EXISTS` | exact |
| `paaf_trace/store.py` (+ `HandoffEvent` dataclass with `as_sql()`) | model / event | CRUD (append) | itself — `RunEvent`/`ToolCallEvent` | exact |
| `tests/test_mesh.py`, `tests/test_handoff.py` **NEW** | test | — | `tests/test_fallback.py` (negative-control discipline, programmed fake) | exact |
| `tests/test_observer.py` **NEW** | test | — | `tests/test_fallback.py` + `tests/test_agent_turn.py` | role-match |
| `tests/test_profiles.py`, `tests/test_compose.py`, `tests/test_ports.py`, `tests/test_inspector.py`, `paaf-trace/tests/test_trace_*.py` (widened) | test | — | themselves | exact |

## Pattern Assignments

### `paaf_llm/ports.py` — additive port types (port, transform)

**Analog:** itself. Every new type must be a frozen slotted dataclass or a `runtime_checkable`
Protocol, and every new exception must justify its taxonomy placement in its own docstring.

**Value-type pattern** (`ports.py:57-81`) — frozen + slots + a docstring saying *why* frozen:

```python
@dataclass(frozen=True, slots=True)
class Message:
    """One turn of conversation, as PAAF represents it.

    Frozen because the message list crosses the port into third-party code: an
    adapter must not be able to rewrite what the user said on the way out, and
    the trace must be able to record the same object the model was handed.
    """

    role: Role
    content: str
```

`ToolSpec` / `ToolCall` / `HandoffRequest` copy this shape exactly. `ToolSpec` and `ToolCall` also
cross the port into third-party adapter code, so the "frozen because it crosses the port" rationale
transfers verbatim.

**Protocol pattern** (`ports.py:206-235`) — `@runtime_checkable`, docstring naming SC#1, and a
`last_*()` post-aggregation read with its rationale inline:

```python
@runtime_checkable
class ChatAdapter(Protocol):
    """The durable contract every model backend is reached through. ..."""

    def stream(
        self, profile: ModelProfile, messages: Sequence[Message]
    ) -> AsyncIterator[str]: ...

    def last_usage(self) -> Usage:
        """Return token usage for the most recently completed stream.

        Read AFTER aggregation, never per chunk: several providers only report
        usage on the final message, so sampling mid-stream yields ``None`` or a
        partial count (SPIKE-05).
        """
        ...
```

`ToolCallingChatAdapter(ChatAdapter, Protocol)` copies this: `@runtime_checkable` (the engine
feature-detects with `isinstance`), and `last_tool_calls()` copies `last_usage()`'s docstring shape
including the "read AFTER aggregation, never per chunk" sentence.

**Exception-taxonomy pattern** (`ports.py:146-179`) — the placement argument is the docstring:

```python
class AllProvidersFailed(Exception):
    """Every profile in the ordered chain degraded — the turn cannot be served.

    Terminal, and pointedly NOT an :class:`AdapterError`: an ``AdapterError``
    means "try the next profile", whereas this means there is no next profile.
    Subclassing it under ``AdapterError`` would let a fallback loop swallow the
    end of the chain as one more hop.
    """


class EngineError(Exception):
    """A configuration or unknown failure — NOT a degraded provider.
    ...
    It lives HERE, in the port, rather than beside the real adapter that raises
    it, and that placement is load-bearing rather than tidy. The adapter package
    is behind an optional extra and is unimportable without the agent framework,
    so a caller running framework-uninstalled — the CLI — could not name this
    class in an ``except`` clause at all if it were defined there.
    """
```

`UndeclaredPeer(Exception)` copies this **exactly**: a sibling of `AllProvidersFailed`/`EngineError`,
never an `AdapterError` subclass, with a docstring stating (a) why it is not an `AdapterError` (the
fallback loop would swallow a routing violation and print `↳ fell back to cloud (connection)` at a
routing bug) and (b) why it lives in `ports.py` (the framework-free CLI must name it in `except`).

**The stale alias to remove** (`ports.py:41-50`) — Phase 4 replaces this placeholder with the real
type; leaving it would keep `TurnResult.handoff` untyped:

```python
if TYPE_CHECKING:
    from typing import Any
    from .profiles import ModelProfile

    # The Phase-4 handoff payload. It does not exist yet, by design: ...
    type HandoffRequest = Any
```

**Module-docstring obligation** (`ports.py:27-31`): the existing "Phase-4 seam (design-only)"
paragraph describes `TurnResult.handoff` as always-`None`. That paragraph must be rewritten, not left
lying.

---

### `paaf_llm/profiles.py` — new mesh config fields (config schema, transform)

**Analog:** itself. Three mechanical conventions, all load-bearing.

**Field pattern with reload tier + a comment naming the tier's justification** (`profiles.py:92-106`):

```python
    # --- inert mesh seam (MODEL-05, D-07/D-08): validated data, no behavior ---
    # WARM: natural-language capability manifest. FREE TEXT ONLY.
    capabilities: str = Field(
        "", json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM: names of profiles this one MAY hand off to. Inert in Phase 3;
    # Phase 4 (MESH-02) reads it to constrain handoff targets.
    peers: list[str] = Field(
        default_factory=list, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
```

Every new field (`ModelProfile.fallback_chain`, `.system_prompt`, `.persona`,
`LlmConfig.default_agent`, `.hop_budget`, observer window settings) carries `json_schema_extra=
{"reload_tier": ...}` plus a one-line `# TIER: why` comment. Also note the `# --- ... ---` section
banner convention; the mesh seam comment now says "inert" and must be updated.

**`extra="forbid"` on both models** (`profiles.py:41`, `profiles.py:197`) — `model_config =
{"extra": "forbid"}` with the T-03-02 rationale in the class docstring. New fields do not change
this; the negative control at `tests/test_profiles.py:324` (a plausible `routing_rules` key) must be
extended in spirit to the new mesh fields.

**Validate-on-read-never-repair** (`profiles.py:131-165`) — errors name the offending value:

```python
    @model_validator(mode="after")
    def _check_endpoint(self) -> ModelProfile:
        """Reject a malformed endpoint declaration at LOAD, and never repair one.
        ...So a malformed path is *reported* — named, with the offending value —
        rather than stripped, prepended, or rewritten into something plausible.
        """
        if not path.startswith("/"):
            raise ValueError(f"endpoint_path {path!r} must start with '/'")
```

**Reference validation** (`profiles.py:210-242`) — the exact loop the four new `_check_refs` rules
extend (`default_agent` resolves; reserved `observer` is not in any `peers`, not `active_profile`,
not in any `fallback_chain`; per-profile `fallback_chain` entries resolve and exclude self):

```python
    @model_validator(mode="after")
    def _check_refs(self) -> LlmConfig:
        """Reject any name that does not resolve to a declared profile. ..."""
        names = set(self.profiles)

        if self.active_profile not in names:
            raise ValueError(
                f"active_profile '{self.active_profile}' is not a declared profile"
            )

        for profile_name, profile in self.profiles.items():
            for peer in profile.peers:
                if peer == profile_name:
                    raise ValueError(f"profile '{profile_name}' lists itself as a peer")
                if peer not in names:
                    raise ValueError(
                        f"profile '{profile_name}'.peers references "
                        f"undeclared profile '{peer}'"
                    )

        return self
```

**Docstring obligation** (`profiles.py:186-195`): `LlmConfig`'s class docstring already explains why
`fallback_chain` and `peers` are separate. D-09's `default_agent` is the *third* such concept and the
docstring must be extended to say so in the same voice ("Collapsing them would quietly make every
fallback target a handoff target").

---

### `paaf_llm/mesh.py` **NEW** (utility, pure transform)

**Analog:** `paaf_llm/compose.py` — the repo's only other pure, stdlib-only, no-I/O, no-state module.

**Module-header pattern** (`compose.py:1-32`): SPDX line, then a docstring that opens with the
requirement IDs it implements, states the *one* invariant the module exists to make mechanical, and
closes with the import-discipline sentence:

```python
# SPDX-License-Identifier: Apache-2.0
"""PERS-01/02/05: the one composer that builds the system prompt actually sent.
...
The module is stdlib-only by design: it imports no agent framework and no other
PAAF package, so the prompt the user audits cannot depend on anything swappable.
"""
```

`mesh.py` opens `"""MESH-01/02/04: ..."""` and carries the same closing sentence (it is the
framework-free half of the mesh, and SC#5 depends on that).

**Pure-class pattern** (`compose.py:58-62`): `"""...Pure and deterministic: same inputs, same bytes
out, no I/O and no state."""` — the peer guard and explainer generator must be pure functions or a
pure class for the same testability reason.

**Guard error-message style** — copy `profiles.py`'s "name the offending value" convention, checking
against `awake.peers` and never against `LlmConfig.profiles` (per RESEARCH Code Example 4 / Pitfall 4):

```python
raise UndeclaredPeer(
    f"{awake_name!r} attempted a handoff to {target!r}, which is not in "
    f"its declared peers {sorted(awake.peers)}"
)
```

---

### `paaf_llm/observer.py` **NEW** (service, request-response)

**Analog:** `paaf_llm/agent.py` — the only other module that drives an adapter and classifies the
result. Note the observer call is a *normal* profile stream through the same port, so it reuses
`_run_chain`-style code rather than inventing a second calling path.

**Protocol-for-a-narrow-collaborator pattern** (`agent.py:74-93`) — declare tiny Protocols rather
than typing against a concrete class; the observer's verdict sink and its tool grant should follow:

```python
class TraceSink(Protocol):
    """The one method the engine needs from a trace store: fire-and-forget emit.

    Narrow on purpose. The engine drains provenance into ``paaf-trace``, but it
    should not be *typed against* the whole store — a sink is the contract, and
    a test can satisfy it with four lines.
    """

    def emit(self, event: object) -> None: ...
```

The D-05 correction signal ("light a flashlight") should be a Protocol of this exact shape — one
synchronous, fire-and-forget method, documented as such — so Phase 10's WebSocket channel can satisfy
it without `paaf_llm` knowing about WebSockets.

**Verdict enum pattern** (`ports.py:84-96`) — a `str` Enum so a verdict serializes into trace JSON
and prints in the CLI without a lookup table:

```python
class FallbackReason(str, Enum):
    """Why the engine moved on from a profile (MODEL-03/04, D-04/D-05).

    A ``str`` enum so a reason serializes into the trace's JSON fallback trail
    and prints in the CLI's ``↳ fell back to <profile> (<reason>)`` notice
    without a lookup table.
    """

    CONNECTION = "connection"  # hard reach failure (MODEL-03)
```

Observer verdicts (`approve` / `generic_retry` / `reroute`) copy this exactly.

---

### `paaf_llm/compose.py` — the `mesh_fragments` parameter (utility, transform)

**Analog:** itself. The byte-exact invariant must survive.

**Current shape** (`compose.py:64-86`) — the two methods and the join contract:

```python
SEGMENT_SEPARATOR = "\n\n"

    def segments(
        self, base_prompt: str, fragments: list[tuple[str, str]]
    ) -> list[Segment]:
        segs = [Segment("base", base_prompt)]
        segs += [Segment(f"skill:{name}", text) for name, text in fragments]
        return segs

    def compose(self, base_prompt: str, fragments: list[tuple[str, str]]) -> str:
        segs = self.segments(base_prompt, fragments)
        return SEGMENT_SEPARATOR.join(s.text for s in segs)
```

Add `mesh_fragments: list[tuple[str, str]] = ()` as a third ordered parameter on **both** methods
(RESEARCH Code Example 3). `compose` must remain `SEGMENT_SEPARATOR.join(s.text for s in
self.segments(...))` — one expression, no branches — because `tests/test_compose.py:74` splits the
output back apart and demands it equal `[base, *fragments]`; Phase 4 widens that to
`[base, *fragments, explainer]` and must not delete it.

**`Segment.source` label convention** (`compose.py:44-55`): `"base"` and `f"skill:{name}"`. The
explainer becomes a new namespaced label in the same style (`"mesh:explainer"`). The docstring's
`text` rule — "as sent — never a summary or a rewrite" — applies to the explainer verbatim.

**Docstring obligation** (`compose.py:26-28`): the module docstring already promises "Phase 4's
generated handoff explainer must also appear here verbatim". Fulfil it and update the tense.

---

### `paaf_llm/agent.py` — the handoff loop (engine loop, event-driven)

**Analog:** itself. The mesh loop wraps `_run_chain`; it does not replace it.

**Per-agent chain — the one method that changes shape** (`agent.py:141-159`):

```python
    def _chain(self) -> list[tuple[str, ModelProfile]]:
        """Return ``[(name, profile), ...]`` in the user's declared order.

        The NAME is carried alongside the profile because it is not *on* it:
        a profile's name is the key it sits under in ``LlmConfig.profiles`` and
        does not cross the adapter port. ...
        """
        names = [self._config.active_profile, *self._config.fallback_chain]
        return [(name, self._config.profiles[name]) for name in names]

    def system_prompt(self) -> str:
        """Return THE system prompt for the next turn (D-02 — one composer). ..."""
        return self._composer.compose(self._config.base_prompt, self._skill_fragments)
```

SC#4 turns `_chain()` into `_chain(agent_name)` → `[awake, *awake.fallback_chain]`, and
`system_prompt()` into `system_prompt(agent_name=None)` resolving that agent's `system_prompt` /
`persona` / explainer. **Keep the "name carried alongside the profile" rule** — it is why `served_by`
works, and the handoff target is a name, not a profile.

**Turn shape to wrap** (`agent.py:178-209`) — the fresh-message-list construction is MESH-03's
guarantee and Pitfall 1's escape; each handoff leg rebuilds it, and no framework message list is
reused:

```python
    async def turn(self, user_text: str) -> TurnResult:
        system = self.system_prompt()
        messages: list[Message] = [
            Message("system", system),
            *self.history,
            Message("user", user_text),
        ]

        started_at = time.time()
        served_by, reply, trail = await self._run_chain(messages)

        # SPIKE-05: read usage ONCE, after the stream fully aggregated. ...
        usage: Usage = self._adapter.last_usage()
        self._drain(system, served_by, trail, usage, started_at, time.time())

        self.history.append(Message("user", user_text))
        self.history.append(Message("assistant", reply))

        return TurnResult(
            text=reply, served_by=served_by, usage=usage,
            fallback_trail=trail, handoff=None,  # Phase-4 seam, inert here
        )
```

Note: history is appended **only after a successful turn** ("a turn that nobody answered is never
appended") — the handoff loop must preserve that, and must never append the handoff tool call.

**Fallback-loop pattern to leave intact** (`agent.py:252-296`) — the mesh wraps this, does not edit
its semantics:

```python
        for index, (name, profile) in enumerate(chain):
            next_name = chain[index + 1][0] if index + 1 < len(chain) else ""
            gen = self._adapter.stream(profile, messages)
            try:
                # The deadline covers ONLY time-to-first-token (D-04/D-05).
                async with asyncio.timeout(profile.first_token_budget_s):
                    first = await gen.__anext__()
            except TimeoutError:
                trail.append((name, next_name, FallbackReason.SLOW_FIRST_TOKEN.value))
                aclose = getattr(gen, "aclose", None)
                if aclose is not None:
                    await aclose()
                continue
            except AdapterError as exc:
                trail.append((name, next_name, exc.reason.value))
                continue
            ...
            # Committed: this profile serves the turn. No mid-stream fallback.
            tokens = [first]
            async for token in gen:
                tokens.append(token)
            return name, "".join(tokens), trail
```

The tool-calling variant (`stream_with_tools`) must keep the `asyncio.timeout` around **only the
first `__anext__`**, the `aclose`-if-present guard, and the "committed, no mid-stream fallback" rule.
`isinstance(adapter, ToolCallingChatAdapter)` selects which stream method to call.

**Trace drain pattern** (`agent.py:211-250`) — synchronous fire-and-forget emit, JSON into TEXT:

```python
        if self._trace is None:
            return
        self._trace.emit(
            RunEvent(
                prompts=system, model=served_by, started_at=started_at,
                ended_at=ended_at, prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens, served_by=served_by,
                fallback_trail=json.dumps(
                    [{"from": frm, "to": to, "reason": reason}
                     for frm, to, reason in trail]
                ),
            )
        )
```

One `RunEvent` **per agent leg** (RESEARCH Finding 5), plus `HandoffEvent`s for attempts/verdicts,
all correlated by an engine-generated `uuid4` `turn_id`. The `if self._trace is None: return` guard
and the "an empty trail writes `"[]"` rather than NULL" rule both carry over.

---

### `paaf_llm/fake/__init__.py` — scripted tool calls (test double, streaming)

**Analog:** itself.

**Program dataclass + `program()`** (`fake/__init__.py:57-118`) — add `tool_calls` as one more
keyword with a docstring `Args:` entry in the same voice:

```python
@dataclass(slots=True)
class _Program:
    """One profile's scripted behavior for a single :meth:`FakeAdapter.stream`."""

    tokens: list[str] = field(default_factory=list)
    fail: type[AdapterError] | None = None
    first_token_delay_s: float = 0.0
    usage: Usage = DEFAULT_USAGE

    def program(self, profile_name: str, *, tokens=None, fail=None,
                first_token_delay_s: float = 0.0, usage=None) -> None:
        """Script what ``profile_name`` does on its next (and every) stream.

        Args:
            profile_name: the profile this script answers for.
            ...
            first_token_delay_s: seconds to wait before the FIRST token. The
                engine's deadline decides whether that is too slow; this adapter
                never does (D-04/D-05).
        """
```

**Recording seam** (`fake/__init__.py:86-89`, `:130`) — the pattern for the new `tool_offers` list
that lets a test prove the peer graph shaped the surface:

```python
        #: Every ``(profile_key, messages)`` this adapter was asked to stream, in
        #: order — the substrate for multi-turn history and composed-prompt
        #: assertions (a test can prove what actually crossed the port).
        self.calls: list[tuple[str, tuple[Message, ...]]] = []
        ...
        key = self.program_key(profile)
        self.calls.append((key, tuple(messages)))
```

**Publish-after-drain rule** (`fake/__init__.py:148-154`) — `last_tool_calls` must be set in the same
place and for the same reason `_last_usage` is:

```python
        for token in program.tokens:
            yield token

        # Usage is published only after the whole stream drained — several real
        # providers report it on the final message only (SPIKE-05), so reading it
        # mid-stream would be an anti-pattern this fake must not reward.
        self._last_usage = program.usage
```

**Fail-loudly rule** (`fake/__init__.py:132-138`): an unprogrammed profile raises `LookupError`
(pointedly not an `AdapterError`) with the programmed-profile list in the message. Anything new the
fake can be asked for should fail the same way rather than default to empty.

**Framework-free constraint** (module docstring, `fake/__init__.py:1-12`): asserted by
`tests/test_fake_adapter.py:154` against this file's source text. `ToolSpec`/`ToolCall` come from
`..ports`, never from anywhere else.

---

### `paaf_llm/cli.py` — `paaf prompt --agent <name>` + tool-surface rendering (CLI, request-response)

**Analog:** the existing `prompt` command (`cli.py:541-573`) — copy the option decorator, the
opt-in-annotation philosophy, and the `nl=False` byte-exactness rule:

```python
@main.command()
@_config_option
@click.option(
    "--provenance",
    is_flag=True,
    help="Label each part of the prompt with its source (base / skill:<name>).",
)
def prompt(config_path: str, provenance: bool) -> None:
    """Print the exact system prompt your model receives. No model is called.

    A pure dry run: no adapter is constructed and no network is touched, ...
    The default output is the composed prompt and nothing else — the trailing
    newline is omitted deliberately so ``paaf prompt --config x.yaml > sent.txt``
    captures the exact bytes (PERS-04).

    ``--provenance`` shows the SAME content with source labels (D-03). It is
    opt-in because the raw view is the authoritative one; annotation is an audit
    aid laid around the prompt, never a rendering of it.
    """
    config = load_llm_config(config_path)
    # The same fragment source build_agent hands the agent — one call, so the
    # inspector cannot show a prompt assembled from different parts (D-02).
    fragments = load_skill_fragments(config)
    composer = PromptComposer()

    if provenance:
        for segment in composer.segments(config.base_prompt, fragments):
            click.echo(PROVENANCE_LABEL.format(source=segment.source))
            click.echo(segment.text)
        return

    # No prefix, no suffix, no newline: stdout IS the prompt (PERS-04/05, D-10).
    click.echo(composer.compose(config.base_prompt, fragments), nl=False)
```

D-19: add `--agent <name>` as a second `click.option` with a default of `None` meaning "the active
agent, exactly as today". The `--agent` value must be validated against `config.profiles` and fail
through `_config_failure` (`cli.py:150`), not with a `KeyError`. The bound mesh tool surface is
rendered under `--provenance` (Finding 1) — it is steering text, so it must be labelled like a
segment, and the "no prefix, no suffix, no newline" default-output rule stays untouched.

**Notice-constant + printer pattern** (`cli.py:364-372`) — the shape D-10 explicitly declines to copy
for handoffs. Reference it in the plan as the anti-pattern, not the pattern:

```python
def _print_fallback_trail(
    trail: Sequence[tuple[str, str, str]], console: Console
) -> None:
    """Print one brief notice per hop the turn took (D-06)."""
    for _frm, to, reason in trail:
        console.print(
            FALLBACK_NOTICE.format(to=to or NO_FALLBACK_TARGET, reason=reason),
            style="yellow",
        )
```

Handoff is **silent** in the reply stream (D-10). The one thing the CLI *must* print is D-07's
"running unobserved" startup line — model it on `render_profiles` (`cli.py:327`) / the existing
startup render, not on the per-turn fallback notice.

**Console rules** (`cli.py:352-361`): `Console(markup=False, highlight=False, soft_wrap=True)` — any
new rendering of user-authored text (capability manifests, explainers, tool descriptions) goes
through `_make_console()` for the stated reason: rich markup in a manifest could restyle or swallow
surrounding output.

**Error handling** (`cli.py:400-417`): the `except AllProvidersFailed / EngineError / AdapterError`
ladder in `_chat_loop`, each clause with a comment explaining why it does not duplicate the fallback
loop. `UndeclaredPeer` gets a new clause here, with the same comment discipline.

---

### `paaf_llm/_engine/__init__.py` — `bind_tools` translation (adapter, streaming)

**Analog:** itself. This is the only file that may name framework types (import-linter enforced).

**The stream to copy** (`_engine/__init__.py:511-547`) — `stream_with_tools` is this method plus a
`bind_tools` call and one extra post-drain assignment:

```python
    async def stream(
        self, profile: ModelProfile, messages: Sequence[Message]
    ) -> AsyncIterator[str]:
        model = self.bind(profile)
        framework_messages = self._to_framework_messages(messages)
        aggregate: Any = None

        try:
            async for chunk in model.astream(framework_messages):
                aggregate = chunk if aggregate is None else aggregate + chunk
                # str() is not decoration: `.text` is a framework TextAccessor
                # (a str subclass), and letting it cross the port would leak a
                # framework type through a PAAF-typed stream (MODEL-08).
                text = str(getattr(chunk, "text", "") or "")
                if text:
                    # Empty chunks are dropped so the engine's first-token
                    # deadline measures real content: ...
                    yield text
        except Exception as exc:  # translated to a PAAF type just below
            # GeneratorExit and CancelledError are BaseException and pass
            # through untouched, which is what lets the engine's timeout
            # aclose() this generator cleanly.
            raise self._translate(exc) from exc

        self._last_usage = self._usage_of(aggregate)
```

Non-negotiables to carry over: the `str(...)` port-leak guard, the empty-chunk drop, the bare
`except Exception` + `self._translate(exc) from exc` boundary (never `BaseException`), and the
post-loop publish.

**Aggregate-read pattern** (`_engine/__init__.py:495-509`) — `_tool_calls_of` is the twin of this
static method, same docstring shape (state what goes wrong with a mid-stream read, and why inventing
a value would make the trace lie):

```python
    @staticmethod
    def _usage_of(aggregate: Any) -> Usage:
        """Read token counts off the AGGREGATED stream, never off a chunk.

        SPIKE-05: Ollama publishes usage on roughly one chunk in 334, so a
        per-chunk read reports ``None`` almost always. ...
        """
        metadata = getattr(aggregate, "usage_metadata", None) or {}
        return Usage(
            prompt_tokens=metadata.get("input_tokens"),
            completion_tokens=metadata.get("output_tokens"),
        )
```

**Translation boundary** (`_engine/__init__.py:481-493`) — every framework exception becomes an
`AdapterError` subclass or `EngineError`, scrubbed of resolved secrets via `_scrub`
(`_engine/__init__.py:468-479`). A `bind_tools` failure is a config problem → `EngineError`.

**Message translation** (`_engine/__init__.py:460-466`) — `_to_framework_messages` builds framework
messages **anew on every call**. Pitfall 1's guarantee depends on this staying true; no leg may reuse
another leg's list.

---

### `paaf_trace/schema.sql` + `store.py` — the handoff chain (schema + event model, append CRUD)

**Analog:** the `runs` / `tool_calls` tables and `RunEvent` / `ToolCallEvent`.

**Table pattern** (`schema.sql:8-31`) — `CREATE TABLE IF NOT EXISTS`, one trailing `--` comment per
column naming its requirement ID, and a block comment justifying denormalization:

```sql
CREATE TABLE IF NOT EXISTS runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prompts             TEXT,      -- the prompt(s) sent to the model (TRACE-02)
    ...
    -- Fallback provenance (MODEL-04, D-06, SC#4). Denormalized onto runs rather than a
    -- child fallbacks table: the fire-and-forget writer never surfaces lastrowid, so an
    -- FK child would force a writer redesign (RESEARCH Pitfall 5). Both are additive and
    -- nullable — a run that never fell back simply leaves them NULL.
    served_by           TEXT,      -- profile name that ACTUALLY served the run (SC#4)
    fallback_trail      TEXT       -- JSON list of fallback hops: [{from,to,reason}]
);
```

**Critical constraint (Pitfall 5):** the writer's only schema step is `await
db.executescript(read_schema())` (`store.py:159`) — no version table, no `ALTER TABLE`. Adding a
column to an existing `CREATE TABLE` block is a **silent no-op** on any developer's existing
`trace.db`. Route (A): **new tables only** (`handoffs`, and `turn_legs` if needed), correlated by an
engine-generated `turn_id` TEXT column, **no FK** to `runs` (the writer never surfaces `lastrowid`).
Note the existing `PRAGMA foreign_keys=ON` at `store.py:29-34`.

**Event dataclass pattern** (`store.py:37-95`) — `@dataclass(slots=True)`, all-optional fields
defaulting to `None`, `as_sql()` returning `(sql, params)`:

```python
@dataclass(slots=True)
class ToolCallEvent:
    """A single tool invocation belonging to a run: name, args, results."""

    run_id: int
    name: str
    args: str | None = None
    results: str | None = None

    def as_sql(self) -> tuple[str, tuple[object, ...]]:
        return (
            "INSERT INTO tool_calls (run_id, name, args, results) VALUES (?, ?, ?, ?)",
            (self.run_id, self.name, self.args, self.results),
        )
```

`HandoffEvent` copies this exactly. The writer is event-agnostic (`store.py:167`: `sql, params =
event.as_sql()`), so **no change to `TraceStore` itself is needed** — adding an event type is a
dataclass plus a `CREATE TABLE`.

---

### Test files (test)

**Analog:** `tests/test_fallback.py` (module docstring at `:1-20`) — the negative-control discipline
the mesh suite must copy:

```python
"""MODEL-03/04 + D-06: losing a provider must not lose the conversation.
...
The negative controls matter as much as the triggers. ``test_healthy_no_fallback``
proves the loop does not fall back when it must not, and
``test_no_mid_stream_fallback`` proves the deadline is time-to-FIRST-token rather
than a stopwatch on the whole reply. Without them, an engine that always fell
back — or one that aborted long healthy answers — would pass every positive test
in this file.
"""
```

Mesh pairs required by CONTEXT: guard fires on an undeclared target / a declared target is not
blocked; the hop budget stops a loop / a legitimate A→B→A hand-back still works; the observer vetoes
a bad handoff / does not veto a good one; an unobserved mesh says it is unobserved.

**Exhaustiveness-meta-test pattern** (`tests/test_fallback.py:203-221`) —
`test_every_fallback_reason_has_a_trigger_in_this_file` and
`test_adapter_error_subclasses_are_all_exercised` walk the enum/class hierarchy against the file's own
source. Copy this for observer verdicts and for handoff outcomes: a new verdict added without a test
should turn the suite red.

**Source-text import assertion** (`tests/test_ports.py:123`, `test_agent_turn.py:140`,
`test_fake_adapter.py:154`) — `test_<module>_source_imports_no_agent_framework` reads the module's own
source text. `mesh.py` and `observer.py` each need one.

**Fixtures** (`tests/conftest.py:30-99`) — `fake_adapter`, `make_profile`, `make_llm_config`,
`trace_store`. `make_llm_config` currently takes `(active, fallbacks, base_prompt)`; the mesh suite
needs peers/observer/`default_agent` support, added in the same "the fixture cannot hand back a config
the schema would refuse" spirit (`conftest.py:63-68`).

**Schema-assertion pattern** (`paaf-trace/tests/test_trace_fallback_schema.py`) — the four-test shape
to copy for the `handoffs` table: columns exist with declared types (via `PRAGMA table_info`),
`as_sql()` is placeholder/param balanced (`sql.count("?") == len(params)`), a real
`TraceStore` write/read round-trip with `assert store.dropped == 0`, and a backward-compat control.
Add the Pitfall-5 verification: run against the **same DB file twice**, since the `tmp_path` fixture
never catches a missing migration.

**CLI test pattern** (`tests/test_inspector.py:1-27`) — the three-way byte comparison (stdout vs
`compose()` vs the `system` message read back off `FakeAdapter.calls`) is the PERS-05 enforcement
shape; the mesh tool surface must be proven visible the same way, not by comparing the CLI to itself.

## Shared Patterns

### Docstring-as-rationale (applies to every file)
**Source:** `ports.py:99-113`, `agent.py:1-42`, `profiles.py:1-23`, `compose.py:1-32`
**Apply to:** every new module, class, and non-obvious line.
This codebase's defining convention: a module docstring opens with the requirement IDs it implements
and states *why the design is this way and not the obvious alternative*; inline comments name the
decision ID (D-xx), requirement (MESH-xx), threat (T-03-xx), or spike (SPIKE-05) they enforce. Code
without this reads as foreign here.

### Framework-free by assertion
**Source:** `ports.py:20-25`, `fake/__init__.py:1-12`, `agent.py:11-13`
**Apply to:** `ports.py`, `mesh.py`, `observer.py`, `fake/`, `compose.py`, `cli.py`, all tests
```
**ZERO framework imports.** This module imports nothing but the standard library
(``ModelProfile`` is referenced under ``TYPE_CHECKING`` only). That is what lets
the shipped :class:`~paaf_llm.fake.FakeAdapter` — and therefore the entire test
suite — run with the agent framework uninstalled (SC#1). ``tests/test_ports.py``
asserts it against this file's source text, and import-linter asserts it against
the import graph.
```
Enforced twice: a source-text test per module, and import-linter on the graph (whitelist is exactly
`paaf_llm._engine` + `paaf_llm._engine.**` — no carve-out is permissible).

### `from __future__ import annotations` + `TYPE_CHECKING` imports
**Source:** every module, e.g. `agent.py:44-66`, `fake/__init__.py:34-44`
**Apply to:** all new modules. Runtime imports stay minimal; `ModelProfile`/`LlmConfig` are imported
under `if TYPE_CHECKING:` wherever only annotations need them.

### SPDX header
**Source:** line 1 of every `.py` and `.sql` file: `# SPDX-License-Identifier: Apache-2.0` /
`-- SPDX-License-Identifier: Apache-2.0`
**Apply to:** `mesh.py`, `observer.py`, every new test file.

### Public-surface re-export discipline
**Source:** `paaf_llm/__init__.py:1-60`
**Apply to:** `ToolSpec`, `ToolCall`, `HandoffRequest`, `ToolCallingChatAdapter`, `UndeclaredPeer`
```python
from .ports import (
    AdapterError, AllProvidersFailed, ChatAdapter, ConnectionFailed, EngineError,
    FallbackReason, Message, RateLimited, RequestTimedOut, Role, ServerError,
    TurnResult, Usage,
)
from .profiles import LlmConfig, ModelProfile

__all__ = [ ... alphabetically sorted ... ]
```
`__all__` is alphabetically sorted. `tests/test_no_leak.py` walks every public signature and fails if
an annotation resolves to a framework module; `tests/test_ports.py:131` asserts the re-export set.
The adapter package must never be imported here (it stays lazy).

### Capability removal over instruction
**Source:** the mesh's house style, stated in CONTEXT D-04/D-08; the structural precedent is
`ports.py:139-143` (no `AdapterError` exists for `SLOW_FIRST_TOKEN`, so an adapter *cannot* claim it)
**Apply to:** the hop budget (withdraw the handoff tool at zero), the observer's grant (default =
generic-retry tool only). Never a mode flag, never a prompt instruction.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(none)* | — | — | Every Phase-4 file has at least a role-match analog in-repo. |

Two areas have **no direct behavioural precedent** even though their *file* has an analog, and the
planner should lean on RESEARCH rather than the codebase for them:

| Area | Nearest thing in repo | What is genuinely new |
|------|----------------------|-----------------------|
| The tool-call surface (`ToolSpec`/`ToolCall`/`bind_tools`) | `_engine.stream` + `_usage_of` aggregation | The port has no tool vocabulary at all today; `tool_calls` table exists in `schema.sql` but is unused. Follow RESEARCH Code Examples 1–2. |
| The D-05 observable correction signal | `TraceSink` Protocol (`agent.py:85-93`) | No event/callback surface exists in `paaf_llm` beyond the trace sink. `TraceSink`'s narrow-Protocol shape is the right model, but the semantics (a hookable "flashlight" endpoint) are new. |

## Metadata

**Analog search scope:** `packages/paaf-llm/src/paaf_llm/**`, `packages/paaf-llm/tests/**`,
`packages/paaf-trace/src/paaf_trace/**`, `packages/paaf-trace/tests/**`, `packages/paaf-core/**`
**Files scanned:** 49 Python/SQL files enumerated; 13 read in full or targeted
**Pattern extraction date:** 2026-08-07
