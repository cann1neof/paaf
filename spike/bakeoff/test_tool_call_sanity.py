"""The tool-call sanity gate — SPIKE-07's precondition, and A5's falsification test.

This suite has three layers, in increasing cost:

1. **Environment assertions** (fast) — telemetry is off, the daemon is up, the pulled
   tags are local-only and `tools`-capable.
2. **Negative controls** (fast, no model traffic) — hand-built malformed tool calls that
   the validator MUST reject. 01-03 established the rule the hard way: *a gate that
   cannot fail manufactures confidence.* Without these, a validator that returned
   ``ok=True`` unconditionally would produce an identically green run.
3. **The gate itself** (slow) — real traffic to a real local model, `TRIALS` times per
   case, requiring `MIN_RELIABILITY`.

Run with:
    uv run --python spike/bakeoff/.venv/bin/python pytest spike/bakeoff/ -q

Throwaway spike code (SC#5): dies with ``spike/``.
"""

from __future__ import annotations

import pytest

# Imported as `bakeoff.<module>`, not bare: this directory carries an `__init__.py` so its
# conftest cannot shadow `spike/conftest.py`. See `spike/bakeoff/__init__.py` for why.
from bakeoff.tool_call_sanity import (
    BOUND_TOOL_NAMES,
    CAPABILITY_MODEL,
    CASES,
    LATENCY_MODEL,
    MIN_RELIABILITY,
    TELEMETRY_ENV_VARS,
    TRIALS,
    Case,
    assert_local_only,
    assert_telemetry_off,
    capabilities_of,
    installed_models,
    reliability,
    telemetry_env_state,
    validate_tool_call,
)

CASE_BY_NAME = {c.name: c for c in CASES}
ADD = CASE_BY_NAME["add"]
GET_TIME = CASE_BY_NAME["get_time"]


# ---------------------------------------------------------------------------
# 1. Environment — asserted, never assumed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("var", TELEMETRY_ENV_VARS)
def test_telemetry_env_var_is_unset(var: str) -> None:
    """PRIV-02 / T-01-04-TEL: no LangSmith, no Logfire, no OTLP exporter."""
    assert telemetry_env_state()[var] is None, (
        f"{var} is set; framework traffic could leave this machine"
    )


def test_assert_telemetry_off_passes_in_this_environment() -> None:
    assert_telemetry_off()


def test_langsmith_and_logfire_are_present_but_inert() -> None:
    """The exporters ship as hard transitive deps. Presence is fine; egress is not.

    `langchain` pulls `langsmith` and `pydantic-ai-slim` pulls `logfire-api`, so an
    env-var check alone does not establish the no-telemetry posture. This asserts the
    runtime state instead: tracing disabled, and the real `logfire` package (as opposed
    to the `logfire-api` no-op shim) absent.
    """
    import importlib.metadata as md

    from langsmith.utils import tracing_is_enabled

    assert tracing_is_enabled() is False, "LangSmith tracing is enabled"

    with pytest.raises(md.PackageNotFoundError):
        md.version("logfire")  # only the no-op `logfire-api` shim may be installed


def test_ollama_daemon_is_reachable() -> None:
    """Deliberately an error, not a skip: a skip would let the gate pass by absence."""
    models = installed_models()
    assert isinstance(models, list)


@pytest.mark.parametrize("model", [CAPABILITY_MODEL, LATENCY_MODEL])
def test_model_is_pulled_and_tool_capable(model: str) -> None:
    caps = capabilities_of(model)
    assert "tools" in caps, f"{model} cannot do tool calling at all: {caps}"


@pytest.mark.parametrize("model", [CAPABILITY_MODEL, LATENCY_MODEL])
def test_model_is_local_only_not_cloud_routed(model: str) -> None:
    """`qwen3.5:cloud` exists in this family and would silently route off-machine."""
    assert_local_only(model)
    assert "cloud" not in capabilities_of(model)


@pytest.mark.parametrize("model", [CAPABILITY_MODEL, LATENCY_MODEL])
def test_capabilities_are_non_empty_so_the_no_cloud_check_is_not_vacuous(
    model: str,
) -> None:
    """Regression guard for a trap that made the PRIV-02 check silently useless.

    The `ollama` python client 0.6.2 models `/api/tags` with a pydantic schema that has
    no `capabilities` field, so `client.list()` reports `[]` for every model even though
    the daemon does send the key. Written against `list()`, `"cloud" not in caps` passes
    for *every* tag — including a genuinely cloud-routed one. `capabilities_of` therefore
    reads `/api/show` and treats an empty list as an error. This test pins that: if a
    later change reintroduces the `list()` shortcut, the no-cloud assertion goes back to
    being vacuous, and this fails instead.
    """
    caps = capabilities_of(model)
    assert caps, "empty capabilities would make the no-cloud assertion vacuously true"
    assert "tools" in caps and "completion" in caps


def test_ollama_client_list_really_does_drop_capabilities() -> None:
    """Documents *why* the guard above exists, against the installed client version.

    If a future `ollama` client adds the field, this test fails and the workaround can be
    simplified — a deliberate, self-retiring note rather than a comment that rots.
    """
    import ollama

    fields = set(ollama.ListResponse.Model.model_fields)
    assert "capabilities" not in fields, (
        "the ollama client now exposes capabilities on list(); capabilities_of() can be "
        f"simplified. Fields: {sorted(fields)}"
    )


# ---------------------------------------------------------------------------
# 2. Negative controls — proof the gate can fail
# ---------------------------------------------------------------------------

MALFORMED: list[tuple[str, list[dict], Case, str]] = [
    ("prose instead of a call", [], ADD, "no tool call"),
    (
        "two calls when one was asked for",
        [{"name": "add", "args": {"a": 48271, "b": 9384}},
         {"name": "get_time", "args": {}}],
        ADD,
        "exactly 1 tool call",
    ),
    (
        "hallucinated tool name",
        [{"name": "calculate_sum", "args": {"a": 48271, "b": 9384}}],
        ADD,
        "not among the bound tools",
    ),
    (
        "wrong tool selected",
        [{"name": "get_time", "args": {}}],
        ADD,
        "wrong tool selected",
    ),
    (
        "arguments are a JSON string, not a dict",
        [{"name": "add", "args": '{"a": 48271, "b": 9384}'}],
        ADD,
        "expected dict",
    ),
    (
        "missing a required argument",
        [{"name": "add", "args": {"a": 48271}}],
        ADD,
        "missing required argument",
    ),
    (
        "extra argument not in the schema",
        [{"name": "add", "args": {"a": 48271, "b": 9384, "c": 1}}],
        ADD,
        "not in schema",
    ),
    (
        "stringified integer",
        [{"name": "add", "args": {"a": "48271", "b": 9384}}],
        ADD,
        "schema declares 'integer'",
    ),
    (
        "bool smuggled in as an integer",
        [{"name": "add", "args": {"a": True, "b": 9384}}],
        ADD,
        "bool, not an integer",
    ),
    (
        "right shape, wrong values",
        [{"name": "add", "args": {"a": 1, "b": 2}}],
        ADD,
        "expected 48271",
    ),
]


@pytest.mark.parametrize(
    "label,calls,case,expected_fragment",
    MALFORMED,
    ids=[m[0] for m in MALFORMED],
)
def test_validator_rejects_malformed_tool_calls(
    label: str, calls: list[dict], case: Case, expected_fragment: str
) -> None:
    """Each of the ten ways a tool call can be wrong must actually be caught."""
    out = validate_tool_call(calls, case)
    assert not out.ok, f"validator wrongly ACCEPTED: {label}"
    joined = " | ".join(out.failures)
    assert expected_fragment in joined, (
        f"{label}: rejected, but for the wrong reason -> {joined}"
    )


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_validator_accepts_the_correct_call(case: Case) -> None:
    """The complement of the negative controls: a gate that rejects everything is
    equally useless. A correct call must pass cleanly."""
    out = validate_tool_call(
        [{"name": case.expected_tool, "args": dict(case.expected_args)}], case
    )
    assert out.ok, out.failures


def test_bound_tool_names_are_exactly_the_two_trivial_tools() -> None:
    assert BOUND_TOOL_NAMES == {"add", "get_time"}


# ---------------------------------------------------------------------------
# 3. The gate — real traffic to the real local model
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("path", ["raw", "langchain"])
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_capability_model_emits_well_formed_tool_calls(path: str, case: Case) -> None:
    """THE GATE (A5). `qwen3.5:9b` must be right every time on a trivial two-tool case.

    Both the raw `ollama` client and `init_chat_model("ollama:...")` are exercised:
    RESEARCH §Pitfall 8 warns against concluding anything about Ollama through a
    framework without checking the provider first, and if the two ever disagree that
    disagreement is a finding about the adapter, not the model.
    """
    assert_telemetry_off()
    rate, outcomes = reliability(CAPABILITY_MODEL, path, case)
    detail = "; ".join(m for o in outcomes for m in o.failures)
    assert rate >= MIN_RELIABILITY, (
        f"{CAPABILITY_MODEL} via {path} on case {case.name!r}: {rate:.0%} over {TRIALS} "
        f"trials, below the {MIN_RELIABILITY:.0%} bar. SWAP THE MODEL and record the "
        f"reason in raw/bakeoff-provision.md rather than letting SPIKE-06 attribute this "
        f"to the framework. Failures: {detail}"
    )


@pytest.mark.slow
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_latency_model_also_emits_well_formed_tool_calls(case: Case) -> None:
    """`qwen3.5:2b` is SPIKE-08's model and is not exempt from the gate.

    An unmeasured latency model could contribute a tool-call failure to the round-trip
    measurement that would read as a pipeline problem.
    """
    assert_telemetry_off()
    rate, outcomes = reliability(LATENCY_MODEL, "langchain", case)
    detail = "; ".join(m for o in outcomes for m in o.failures)
    assert rate >= MIN_RELIABILITY, (
        f"{LATENCY_MODEL} on case {case.name!r}: {rate:.0%} over {TRIALS} trials. "
        f"Failures: {detail}"
    )


@pytest.mark.slow
def test_raw_provider_reports_token_counts_informational() -> None:
    """Informational, NEVER gating — the answer belongs to SPIKE-05, not to this plan.

    CLAUDE.md flags "token counts come back None for Ollama" as a known rough edge and
    RESEARCH §Pitfall 8 warns against concluding it from a streaming chunk. Recording the
    non-streaming raw-provider answer here means SPIKE-05 starts from a known baseline
    instead of rediscovering it. Following 01-03's pattern, a negative answer is a finding
    to carry forward, not a gate failure — so this test only asserts that the *fields
    exist*, and prints whatever they hold.
    """
    from bakeoff.tool_call_sanity import probe_raw

    out = probe_raw(CAPABILITY_MODEL, ADD)
    assert out.usage is not None
    assert {"prompt_eval_count", "eval_count"} <= set(out.usage)
    print(f"\n[informational] raw provider usage for {CAPABILITY_MODEL}: {out.usage}")
