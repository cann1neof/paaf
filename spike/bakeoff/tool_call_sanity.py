"""Tool-call sanity gate — the capability gate that must pass BEFORE the bake-off runs.

Why this module exists
----------------------
RESEARCH §Assumptions Log A5: *"A weak tool-caller would make MCP tracing hard to observe
for reasons unrelated to the framework."* SPIKE-06 asks whether `langchain-mcp-adapters`
(0.x) and `pydantic-ai.mcp` surface MCP tool arguments and results to a tracer. If the
local model simply never emits a well-formed tool call, **both** adapters look opaque and
the phase would render a verdict on LangChain-vs-Pydantic-AI that is really a verdict on
qwen3.5. This module proves the instrument works before anything is measured with it.

CLAUDE.md §Decision 6 is explicit that the selection criterion is **tool-calling quality,
not chat quality**, and that the community default is `[UNVERIFIED]` and must be
benchmarked at implementation time rather than taken on the roadmap's word. Nothing here
scores prose. The only question asked is: *does a correct, schema-valid tool call come
back, every time, on a case where the right answer is unambiguous?*

What "well-formed" means here
-----------------------------
Seven separate conditions, each independently falsifiable (see ``validate_tool_call``):

1. at least one tool call came back (i.e. not prose),
2. exactly one came back (the prompts admit exactly one),
3. the name is one of the tools that were actually bound,
4. the name is the *expected* one — this tests tool **selection**, not merely emission,
5. the arguments are a dict and are JSON-round-trippable,
6. the argument keys match the schema exactly — no missing, no extras,
7. the argument values have the right types **and the right values**.

A model that emits `add` with `{"a": "48271"}` (string, missing `b`) has emitted a tool
call, and would pass a naive `if response.tool_calls:` check. It fails here.

Both paths are probed
---------------------
`RAW` uses the `ollama` python client directly; `LANGCHAIN` uses
`init_chat_model("ollama:<tag>")`. RESEARCH §Pitfall 8 warns against concluding anything
about Ollama from a framework-mediated observation without checking the provider first.
If the two paths ever disagree, that disagreement is a finding about the *adapter*, and
having both here means 01-06/01-07 can tell the two apart.

Throwaway spike code (SC#5): dies with ``spike/``.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Model tags — pinned, never `latest`. See raw/bakeoff-provision.md §1.4.
# ---------------------------------------------------------------------------

#: Capability model for SPIKE-05/06/07. 9.7B Q4_K_M, 6.6 GB.
CAPABILITY_MODEL = "qwen3.5:9b"

#: Small model for SPIKE-08's latency shape, sized to sit alongside Whisper +
#: Chatterbox inside 18 GB. 2.3B Q8_0, 2.7 GB. Gated too — an unmeasured latency model
#: could contribute a tool-call failure to SPIKE-08 that reads as a pipeline problem.
LATENCY_MODEL = "qwen3.5:2b"

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

#: Trials per (model, path, case). Stock sampling defaults for this family are
#: temperature=1 / top_p=0.95 / top_k=20, so a single success could be luck. Repeating
#: turns a coin flip into a reliability rate. Override with SPIKE_TOOL_TRIALS.
TRIALS = int(os.environ.get("SPIKE_TOOL_TRIALS", "3"))

#: On a *trivial* two-tool case, anything short of perfect is a red flag, not a rounding
#: error. The gate demands 1.0 and the plan's remedy for a miss is to swap the model.
MIN_RELIABILITY = 1.0

#: Env vars that must be unset before any framework import (PRIV-02 / T-01-04-TEL).
#: The first four are the plan's; the rest are the ones the plan's list misses. The OTel
#: entries matter because pydantic-ai's egress path is OpenTelemetry, not a
#: Logfire-branded variable.
TELEMETRY_ENV_VARS = (
    "LOGFIRE_TOKEN",
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
    "LANGSMITH_ENDPOINT",
    "LANGSMITH_PROJECT",
    "LOGFIRE_SEND_TO_LOGFIRE",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
)


# ---------------------------------------------------------------------------
# The two trivial tools, and the cases that disambiguate between them
# ---------------------------------------------------------------------------
# Schemas are written once, in JSON-Schema form, and reused for BOTH the raw client
# (which wants OpenAI-style function specs) and for validation. Deriving the validator's
# expectations from a second, hand-written copy would let the two drift, and a validator
# that checks against a stale schema is a gate that cannot fail.

ADD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "a": {"type": "integer", "description": "First addend."},
        "b": {"type": "integer", "description": "Second addend."},
    },
    "required": ["a", "b"],
}

GET_TIME_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two integers and return their sum.",
            "parameters": ADD_SCHEMA,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current wall-clock time. Takes no arguments.",
            "parameters": GET_TIME_SCHEMA,
        },
    },
]

BOUND_TOOL_NAMES = frozenset(s["function"]["name"] for s in TOOL_SPECS)

#: Maps a JSON-Schema primitive to the Python types that satisfy it. `bool` is excluded
#: from `integer` on purpose: in Python `isinstance(True, int)` is True, so a model
#: answering `{"a": true}` would otherwise slip through as a valid integer.
_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "integer": (int,),
    "number": (int, float),
    "string": (str,),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
}


@dataclass(frozen=True)
class Case:
    """One prompt whose correct response is exactly one specific tool call."""

    name: str
    prompt: str
    expected_tool: str
    expected_args: dict[str, Any]

    @property
    def schema(self) -> dict[str, Any]:
        for spec in TOOL_SPECS:
            if spec["function"]["name"] == self.expected_tool:
                return spec["function"]["parameters"]
        raise KeyError(self.expected_tool)


#: Two cases, one per tool. Using both means the gate measures tool SELECTION: a model
#: that always calls `add` would score 50%, which a single-case gate would miss entirely.
#: The addends are large and arbitrary so the arguments cannot be a memorised constant.
CASES: tuple[Case, ...] = (
    Case(
        name="add",
        prompt="What is 48271 plus 9384? Use the available tools.",
        expected_tool="add",
        expected_args={"a": 48271, "b": 9384},
    ),
    Case(
        name="get_time",
        prompt="What time is it right now? Use the available tools.",
        expected_tool="get_time",
        expected_args={},
    ),
)


# ---------------------------------------------------------------------------
# Validation — a pure function, so the gate can be proven capable of failing
# ---------------------------------------------------------------------------


@dataclass
class Outcome:
    """The verdict on one model response. ``ok`` is True only if ``failures`` is empty."""

    case: str
    path: str
    model: str
    tool_calls: list[dict[str, Any]]
    failures: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    #: Informational, never gating — see `probe_raw` and RESEARCH §Pitfall 8.
    usage: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return not self.failures


def validate_tool_call(
    tool_calls: list[dict[str, Any]],
    case: Case,
    *,
    path: str = "-",
    model: str = "-",
) -> Outcome:
    """Judge a normalised list of tool calls against ``case``.

    ``tool_calls`` is the framework-free shape ``[{"name": str, "args": dict}, ...]``,
    so this function has no LangChain or Ollama import in its reasoning and can be
    exercised against hand-built inputs. That is what makes the negative control in
    ``test_tool_call_sanity.py`` possible: a gate nobody has watched fail is not evidence.
    """
    out = Outcome(case=case.name, path=path, model=model, tool_calls=tool_calls)
    f = out.failures

    # 1. Prose instead of a tool call is the single most likely failure mode.
    if not tool_calls:
        f.append("no tool call returned (model answered in prose or returned nothing)")
        return out

    # 2. The prompts admit exactly one call.
    if len(tool_calls) != 1:
        f.append(f"expected exactly 1 tool call, got {len(tool_calls)}: "
                 f"{[c.get('name') for c in tool_calls]}")
        return out

    call = tool_calls[0]
    name = call.get("name")

    # 3. Hallucinated tool name — a call to something never bound.
    if name not in BOUND_TOOL_NAMES:
        f.append(f"tool name {name!r} is not among the bound tools "
                 f"{sorted(BOUND_TOOL_NAMES)} (hallucinated tool)")
        return out

    # 4. Selection: right shape, wrong tool.
    if name != case.expected_tool:
        f.append(f"wrong tool selected: expected {case.expected_tool!r}, got {name!r}")
        return out

    args = call.get("args")

    # 5a. Arguments must be a mapping...
    if not isinstance(args, dict):
        f.append(f"arguments are {type(args).__name__}, expected dict: {args!r}")
        return out

    # 5b. ...and JSON-round-trippable. A tool call that cannot cross a wire is not
    #     well-formed no matter how it looks in memory.
    try:
        json.loads(json.dumps(args))
    except (TypeError, ValueError) as exc:
        f.append(f"arguments are not JSON-serialisable: {exc}")
        return out

    schema = case.schema
    props: dict[str, Any] = schema.get("properties", {})
    required = set(schema.get("required", []))
    got = set(args)

    # 6. Keys must match the schema exactly, in both directions.
    if missing := required - got:
        f.append(f"missing required argument(s): {sorted(missing)}")
    if extra := got - set(props):
        f.append(f"unexpected argument(s) not in schema: {sorted(extra)}")

    # 7. Types, then values.
    for key, value in args.items():
        declared = props.get(key, {}).get("type")
        expected_types = _JSON_TYPES.get(declared)
        if expected_types is None:
            continue
        if declared == "integer" and isinstance(value, bool):
            f.append(f"argument {key!r} is a bool, not an integer: {value!r}")
            continue
        if not isinstance(value, expected_types):
            f.append(f"argument {key!r} has type {type(value).__name__}, "
                     f"schema declares {declared!r}: {value!r}")

    for key, expected in case.expected_args.items():
        if key in args and args[key] != expected:
            f.append(f"argument {key!r} = {args[key]!r}, expected {expected!r}")

    return out


# ---------------------------------------------------------------------------
# Probes — one per path
# ---------------------------------------------------------------------------


def probe_raw(model: str, case: Case) -> Outcome:
    """Probe the Ollama HTTP API directly via the official `ollama` client.

    RESEARCH §Pitfall 8 and §Supporting both say to confirm the raw provider before
    blaming a framework. `usage` is captured here purely as information for SPIKE-05 —
    it never gates. Per 01-03's pattern, a negative answer on an informational check is
    a finding to carry forward, not a gate failure.
    """
    import ollama

    client = ollama.Client(host=OLLAMA_HOST, timeout=300)
    t0 = time.perf_counter()
    resp = client.chat(
        model=model,
        messages=[{"role": "user", "content": case.prompt}],
        tools=TOOL_SPECS,
    )
    elapsed = time.perf_counter() - t0

    raw_calls = resp["message"].get("tool_calls") or []
    normalised = [
        {"name": c.function.name, "args": dict(c.function.arguments or {})}
        for c in raw_calls
    ]
    out = validate_tool_call(normalised, case, path="raw", model=model)
    out.elapsed_s = elapsed
    out.usage = {
        "prompt_eval_count": resp.get("prompt_eval_count"),
        "eval_count": resp.get("eval_count"),
    }
    return out


def probe_langchain(model: str, case: Case) -> Outcome:
    """Probe through `init_chat_model("ollama:<tag>")` — the string->model factory.

    This is the exact call shape RESEARCH §Code Examples uses and that D-16 maps a YAML
    model profile onto, so the gate exercises the path the product would actually use.
    """
    from langchain.chat_models import init_chat_model
    from langchain_core.tools import tool

    @tool
    def add(a: int, b: int) -> int:
        """Add two integers and return their sum."""
        return a + b

    @tool
    def get_time() -> str:
        """Get the current wall-clock time. Takes no arguments."""
        return "12:00"

    bound = init_chat_model(f"ollama:{model}").bind_tools([add, get_time])
    t0 = time.perf_counter()
    msg = bound.invoke(case.prompt)
    elapsed = time.perf_counter() - t0

    normalised = [
        {"name": c["name"], "args": dict(c.get("args") or {})}
        for c in (msg.tool_calls or [])
    ]
    out = validate_tool_call(normalised, case, path="langchain", model=model)
    out.elapsed_s = elapsed
    out.usage = getattr(msg, "usage_metadata", None)
    return out


PROBES: dict[str, Callable[[str, Case], Outcome]] = {
    "raw": probe_raw,
    "langchain": probe_langchain,
}


def reliability(model: str, path: str, case: Case, trials: int = TRIALS) -> tuple[float, list[Outcome]]:
    """Run ``trials`` independent probes and return (pass rate, outcomes)."""
    outcomes = [PROBES[path](model, case) for _ in range(trials)]
    rate = sum(o.ok for o in outcomes) / len(outcomes)
    return rate, outcomes


# ---------------------------------------------------------------------------
# Environment assertions — things that must be true for the measurement to mean anything
# ---------------------------------------------------------------------------


def telemetry_env_state() -> dict[str, str | None]:
    """Current value of every telemetry variable (``None`` == unset). PRIV-02."""
    return {v: os.environ.get(v) for v in TELEMETRY_ENV_VARS}


def assert_telemetry_off() -> None:
    """Raise if any telemetry variable is set. Called before any model traffic."""
    if leaked := {k: v for k, v in telemetry_env_state().items() if v is not None}:
        raise AssertionError(
            f"telemetry env is SET, violating PRIV-02 / T-01-04-TEL: {sorted(leaked)}. "
            "Unset these before running any framework."
        )


def installed_models() -> list[dict[str, Any]]:
    """Ask the daemon what it has. Raises if the daemon is unreachable — deliberately.

    A skip here would let the gate go green by absence, the failure mode 01-03 designed
    its interpreter-keyed collection guard to prevent.
    """
    import ollama

    return ollama.Client(host=OLLAMA_HOST, timeout=30).list()["models"]


def capabilities_of(model: str) -> list[str]:
    """Declared capabilities of a pulled model, via ``/api/show``.

    ⚠️ **Do not read this from** ``client.list()``. The `ollama` python client 0.6.2
    models the `/api/tags` response with a pydantic schema whose `Model` class declares
    only ``model / modified_at / digest / size / details`` — **no ``capabilities``
    field.** The daemon does send `capabilities` on `/api/tags` (confirmed against the
    raw HTTP endpoint), but pydantic drops the unknown key, so `list()` reports `[]` for
    every model. A `"cloud" not in caps` check written against `list()` therefore always
    passes, for every tag, including a genuinely cloud-routed one — a no-cloud guarantee
    that is vacuously true is worse than none, because it reads as evidence.

    ``client.show()`` uses a different schema which *does* declare `capabilities`, so it
    is the honest source. An empty list is treated as an error below rather than as
    "this model has no capabilities", for the same reason.
    """
    import ollama

    if model not in {m["model"] for m in installed_models()}:
        raise LookupError(
            f"model {model!r} is not pulled. Available: "
            f"{[m['model'] for m in installed_models()]}. Run `ollama pull {model}`."
        )
    caps = list(ollama.Client(host=OLLAMA_HOST, timeout=30).show(model).capabilities or [])
    if not caps:
        raise AssertionError(
            f"the daemon reported NO capabilities for {model!r}. Empty must never be "
            "read as 'not cloud-routed' — it means the capability list could not be "
            "obtained, so the PRIV-02 assertion below would pass vacuously."
        )
    return caps


def assert_local_only(model: str) -> None:
    """Raise if the tag is cloud-routed.

    The qwen3.5 family publishes `qwen3.5:cloud` and `qwen3.5:397b-cloud`, and lists
    `cloud` among its advertised capabilities. Those tags route inference to Ollama's
    hosted service while looking exactly like a local call — a silent violation of the
    project's no-mandatory-cloud promise. The absence of `cloud` in the daemon's reported
    capabilities is the machine-checkable form of that promise.
    """
    caps = capabilities_of(model)
    if "cloud" in caps:
        raise AssertionError(
            f"model {model!r} declares the 'cloud' capability {caps} — inference would "
            "leave this machine. PRIV-02 forbids it. Pull a local tag instead."
        )
    if "tools" not in caps:
        raise AssertionError(
            f"model {model!r} does not declare the 'tools' capability: {caps}"
        )


# ---------------------------------------------------------------------------
# Report — `python spike/bakeoff/tool_call_sanity.py`
# ---------------------------------------------------------------------------


def run_gate(models: tuple[str, ...] = (CAPABILITY_MODEL, LATENCY_MODEL)) -> int:
    assert_telemetry_off()
    print(f"host={OLLAMA_HOST}  trials={TRIALS}  min_reliability={MIN_RELIABILITY}")
    failed = 0
    for model in models:
        assert_local_only(model)
        paths = ("raw", "langchain") if model == CAPABILITY_MODEL else ("langchain",)
        print(f"\n=== {model}  caps={capabilities_of(model)} ===")
        for path in paths:
            for case in CASES:
                rate, outs = reliability(model, path, case)
                mark = "PASS" if rate >= MIN_RELIABILITY else "FAIL"
                mean = sum(o.elapsed_s for o in outs) / len(outs)
                print(f"  [{mark}] {path:9} {case.name:9} {rate:.0%} "
                      f"({sum(o.ok for o in outs)}/{len(outs)})  mean {mean:5.1f}s  "
                      f"usage={outs[-1].usage}")
                for o in outs:
                    for msg in o.failures:
                        print(f"         ! {msg}")
                failed += rate < MIN_RELIABILITY
    print("\nGATE:", "GREEN" if not failed else f"RED ({failed} condition(s) failed)")
    return failed


if __name__ == "__main__":
    raise SystemExit(1 if run_gate() else 0)
