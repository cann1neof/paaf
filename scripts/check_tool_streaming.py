# SPDX-License-Identifier: Apache-2.0
"""NON-BLOCKING live check: does binding tools kill token streaming? (Assumption A1)

**This script gates NOTHING, and that is deliberate.** The entire mesh test suite
runs on ``FakeAdapter``, so phase 4's SC#5 — "the mesh works with the agent
framework uninstalled" — cannot be affected by what a real Ollama box does here.
A negative result is an *engine-adapter latency finding to write down*, not a
phase blocker and not a reason to change the adapter's design. Nothing in CI runs
this file, no test imports it, and it exits 0 in every case including failure.

**Why it is a script and not a test.** The repo's pytest default is
``--disable-socket --allow-unix-socket`` (see ``[tool.pytest.ini_options]`` in the
root ``pyproject.toml``): any AF_INET socket fails the suite. That is the
no-network guarantee working correctly, so a live-Ollama check cannot be a plain
test without punching a hole in it. It lives in ``scripts/``, outside
``testpaths = ["packages"]``, where pytest will not collect it.

**What A1 actually asks.** RESEARCH § Pitfall 3: ``ChatOllama`` historically
returned the whole reply as ONE chunk once tools were bound — which would
silently convert PAAF from a streaming system into a batch one for its primary
local provider, and the mesh binds a handoff tool to essentially every agent.
Upstream issue ``langchain-ai/langchain#26971`` was closed 2025-06-26, well before
the ``langchain-ollama==1.1.0`` this repo pins, and Ollama shipped an incremental
tool-call parser on 2025-05-28. But that is an inference from an issue closure,
not an executed check against these exact pins. This is the executed check.

Three things are measured:

1. **The A1 question.** Chunk count for a plain, non-tool reply WITH a tool bound,
   against the same reply with nothing bound. More than one chunk means tokens
   still stream and A1 is confirmed.
2. **The aggregation.** A prompt that should provoke a handoff, checked through
   ``last_tool_calls()`` — the PAAF port, not the framework — for a ``ToolCall``
   whose ``arguments`` is a parsed dict rather than a JSON fragment.
3. **Rough time-to-first-token**, for comparison against the Phase-1 numbers.

Invocation (both gate models are already pulled on the dev machine)::

    uv run --all-packages --extra engine python scripts/check_tool_streaming.py
    uv run --all-packages --extra engine python scripts/check_tool_streaming.py qwen3.5:2b qwen3.5:9b

Record the verdict in the plan SUMMARY in DECISIONS.md's measurement style: the
pinned versions, the model tag, the chunk counts observed, and an explicit
disposition (``confirmed`` / ``refuted`` / ``not run, and why``).
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from paaf_llm._engine import LangChainAdapter
from paaf_llm.ports import Message, ToolSpec
from paaf_llm.profiles import ModelProfile

if TYPE_CHECKING:
    from collections.abc import Sequence

#: The default gate model — the smaller of the two Phase-1 models, because this
#: check is about chunk COUNT and latency shape, not about answer quality.
DEFAULT_MODELS = ("qwen3.5:2b",)

OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434

#: A handoff tool in the exact shape ``mesh.handoff_tools`` produces: the target
#: is in the NAME and there are no parameters. Using the real shape matters —
#: a tool with arguments would exercise a JSON-reassembly path the mesh never
#: takes, and could pass or fail for reasons A1 is not about.
HANDOFF_TOOL = ToolSpec(
    name="transfer_to_ada",
    description="Hand the conversation to Ada, who answers questions about maths.",
    parameters={},
)

#: A prompt with no plausible reason to call the tool. Its whole job is to
#: produce ORDINARY PROSE while a tool is bound — that is the A1 case.
PLAIN_PROMPT = "In two sentences, describe the colour blue. Do not use any tools."

#: A prompt whose only sensible move is the handoff.
HANDOFF_PROMPT = "I need help with a calculus problem. Please transfer me to Ada."


@dataclass
class Result:
    """One drained stream, in the terms A1 is asked in."""

    label: str
    chunks: int = 0
    first_token_s: float | None = None
    total_s: float = 0.0
    text: str = ""
    tool_calls: tuple[object, ...] = ()
    error: str | None = None


async def _drain(
    adapter: LangChainAdapter,
    profile: ModelProfile,
    prompt: str,
    tools: Sequence[ToolSpec],
    label: str,
) -> Result:
    """Run one stream and count what crossed the port.

    Every failure is caught and recorded rather than raised: a machine with no
    Ollama running must still produce a verdict block saying so, because "not
    run, and why" is a legitimate A1 disposition and a traceback is not.
    """
    result = Result(label=label)
    messages = [Message("user", prompt)]
    started = time.monotonic()
    try:
        stream = (
            adapter.stream_with_tools(profile, messages, tools)
            if tools
            else adapter.stream(profile, messages)
        )
        async for token in stream:
            if result.first_token_s is None:
                result.first_token_s = time.monotonic() - started
            result.chunks += 1
            result.text += token
        if tools:
            result.tool_calls = adapter.last_tool_calls()
    except Exception as exc:  # noqa: BLE001 - a failed probe is a recorded result
        result.error = f"{type(exc).__name__}: {exc}"
    result.total_s = time.monotonic() - started
    return result


def _report(result: Result) -> None:
    if result.error is not None:
        print(f"  {result.label:<22} ERROR  {result.error}")
        return
    ttft = "n/a" if result.first_token_s is None else f"{result.first_token_s:.2f}s"
    print(
        f"  {result.label:<22} chunks={result.chunks:<5} "
        f"ttft={ttft:<7} total={result.total_s:.2f}s"
    )
    if result.tool_calls:
        for call in result.tool_calls:
            print(f"  {'':<22} tool_call -> {call}")


async def check(model: str) -> bool:
    """Measure one model. Returns whether A1 held — for PRINTING, never for exiting."""
    profile = ModelProfile(
        provider="ollama",
        model=model,
        endpoint_host=OLLAMA_HOST,
        endpoint_port=OLLAMA_PORT,
    )
    adapter = LangChainAdapter()

    print(f"\n=== {model} @ http://{OLLAMA_HOST}:{OLLAMA_PORT} ===")
    baseline = await _drain(adapter, profile, PLAIN_PROMPT, (), "plain, no tools")
    with_tools = await _drain(
        adapter, profile, PLAIN_PROMPT, [HANDOFF_TOOL], "plain, tool bound"
    )
    handoff = await _drain(
        adapter, profile, HANDOFF_PROMPT, [HANDOFF_TOOL], "handoff, tool bound"
    )

    for result in (baseline, with_tools, handoff):
        _report(result)

    streamed = with_tools.error is None and with_tools.chunks > 1
    print(
        f"\n  A1 (tokens still stream with a tool bound): "
        f"{'CONFIRMED' if streamed else 'NOT CONFIRMED'}"
    )
    if baseline.error is None and with_tools.error is None:
        print(
            f"  chunk count  {baseline.chunks} without tools -> "
            f"{with_tools.chunks} with a tool bound"
        )

    calls = handoff.tool_calls
    if calls:
        parsed = all(isinstance(getattr(c, "arguments", None), dict) for c in calls)
        print(
            f"  aggregation: {len(calls)} PAAF ToolCall(s), "
            f"arguments parsed to dict: {parsed}"
        )
    elif handoff.error is None:
        # Not a failure of A1: RESEARCH notes some models answer in prose rather
        # than calling. Recorded so the SUMMARY does not overclaim either way.
        print("  aggregation: the model called no tool on the handoff prompt")

    return streamed


async def main(models: Sequence[str]) -> None:
    print(__doc__.splitlines()[0])
    print("This check gates nothing. Exit code is 0 regardless of the outcome.")
    for model in models:
        try:
            await check(model)
        except Exception as exc:  # noqa: BLE001 - see the module docstring
            print(f"\n=== {model} ===\n  ERROR  {type(exc).__name__}: {exc}")
    print("\nRecord the verdict in the plan SUMMARY. Nothing here fails a build.")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(DEFAULT_MODELS)))
    # Explicit and load-bearing: this script must never become a gate.
    sys.exit(0)
