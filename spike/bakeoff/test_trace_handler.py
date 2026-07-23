"""SPIKE-05 Wave-0 unit tests: the trace handler must fire, and must read usage late.

Framework-free by construction — this module imports only ``bakeoff.port`` and the
stdlib-only doubles from ``spike/conftest.py``, so it collects and passes under *any* of
the phase's three venvs. It is the half of SPIKE-05 that can be answered without Ollama:
whether the handler contract is right. Whether Ollama actually returns numbers is a live
measurement and belongs to ``adapter_langchain``/``adapter_pydantic_ai``.

Two failure modes are under test, both of which would produce a **false negative** on the
requirement CLAUDE.md flagged as decision-critical:

1. *The handler never fires.* Chat models fire ``on_chat_model_start``; a handler
   implementing only ``on_llm_start`` records nothing and the spike concludes "prompts are
   not visible" about a handler that was never called.
2. *Usage is read too early.* Ollama emits ``prompt_eval_count``/``eval_count`` only on the
   final ``done: True`` chunk, so every intermediate chunk carries ``None`` (Pitfall 8).

Each is paired with a negative control that demonstrates the wrong answer, because a test
that cannot show the failure cannot claim to have excluded it (01-04).
"""

from __future__ import annotations

import pytest
from conftest import FakeModel

from bakeoff.port import (
    REQUIRED_LANGCHAIN_HOOKS,
    TokenUsage,
    TraceRecorder,
    UsageAggregator,
    UsageReadTooEarly,
    hooks_defined_by,
    missing_hooks,
    naive_stream_usage,
)

# --------------------------------------------------------------------------------------
# Stand-in handler classes. These mimic the *shape* of a langchain AsyncCallbackHandler
# subclass without importing one: a base that provides all six hooks as inherited no-ops,
# and subclasses that override some or all of them. `_FrameworkBase.__module__` is
# rewritten to a framework root so `hooks_defined_by` treats it as the boundary, which is
# what makes these doubles exercise the real MRO-walking logic rather than a special case.
# --------------------------------------------------------------------------------------


class _FrameworkBase:
    """Stands in for ``langchain_core.callbacks.AsyncCallbackHandler``."""

    async def on_chat_model_start(self, *a, **kw): ...
    async def on_llm_start(self, *a, **kw): ...
    async def on_llm_new_token(self, *a, **kw): ...
    async def on_llm_end(self, *a, **kw): ...
    async def on_tool_start(self, *a, **kw): ...
    async def on_tool_end(self, *a, **kw): ...


_FrameworkBase.__module__ = "langchain_core.callbacks.base"


class CompleteHandler(_FrameworkBase):
    """Overrides all six. This is the shape both adapters must ship."""

    def __init__(self) -> None:
        self.trace = TraceRecorder()

    async def on_chat_model_start(self, serialized, messages, **kw):
        self.trace.record_prompt(messages, hook="on_chat_model_start")

    async def on_llm_start(self, serialized, prompts, **kw):
        self.trace.record_prompt(prompts, hook="on_llm_start")

    async def on_llm_new_token(self, token, **kw):
        self.trace.record_token(token)

    async def on_llm_end(self, response, **kw):
        self.trace.record_usage(getattr(response, "usage", None))

    async def on_tool_start(self, serialized, input_str, **kw): ...

    async def on_tool_end(self, output, **kw): ...


class LlmStartOnlyHandler(_FrameworkBase):
    """The anti-pattern: only ``on_llm_start``. Records nothing for a chat model."""

    def __init__(self) -> None:
        self.trace = TraceRecorder()

    async def on_llm_start(self, serialized, prompts, **kw):
        self.trace.record_prompt(prompts, hook="on_llm_start")


class InheritOnlyHandler(_FrameworkBase):
    """Overrides nothing. ``hasattr`` says it has every hook; it records nothing."""


# --------------------------------------------------------------------------------------
# 1. The handler must implement BOTH start hooks — presence is not implementation
# --------------------------------------------------------------------------------------


def test_complete_handler_defines_every_required_hook_itself():
    assert missing_hooks(CompleteHandler) == ()
    assert set(REQUIRED_LANGCHAIN_HOOKS) <= hooks_defined_by(CompleteHandler)


def test_llm_start_only_handler_is_caught_as_missing_the_chat_hook():
    """The negative control for failure mode 1."""
    assert missing_hooks(LlmStartOnlyHandler) == (
        "on_chat_model_start",
        "on_llm_new_token",
        "on_llm_end",
        "on_tool_start",
        "on_tool_end",
    )


def test_hasattr_would_have_passed_the_handler_that_records_nothing():
    """Why ``missing_hooks`` walks the MRO instead of calling ``hasattr``.

    Every ``AsyncCallbackHandler`` subclass *inherits* all six hooks as no-ops, so the
    obvious check is vacuously true for a handler that overrides none of them — the same
    class of vacuous guarantee 01-04 found in the no-cloud assertion.
    """
    assert all(hasattr(InheritOnlyHandler, hook) for hook in REQUIRED_LANGCHAIN_HOOKS)
    assert missing_hooks(InheritOnlyHandler) == REQUIRED_LANGCHAIN_HOOKS


async def test_a_chat_model_start_event_reaches_only_the_complete_handler(fake_model: FakeModel):
    """Drive both handlers with the event a *chat* model actually emits."""
    messages = [[{"role": "user", "content": "what is 48271 + 9384?"}]]

    complete = CompleteHandler()
    await complete.on_chat_model_start({"name": "chat"}, messages)
    assert complete.trace.prompts == (messages,)
    assert complete.trace.prompt_hooks == ("on_chat_model_start",)

    partial = LlmStartOnlyHandler()
    # The chat hook exists (inherited) and is callable — it simply does nothing.
    await partial.on_chat_model_start({"name": "chat"}, messages)
    assert partial.trace.prompts == (), "a chat model would leave this handler blank"

    assert fake_model.call_count == 0, "this contract test must not touch a model"


# --------------------------------------------------------------------------------------
# 2. Usage must be read after aggregation, never off a chunk
# --------------------------------------------------------------------------------------


def _ollama_shaped_stream(model: FakeModel) -> tuple[list[TokenUsage | None], TokenUsage]:
    """Chunk usages shaped exactly like Ollama's: ``None`` until the final ``done`` chunk."""
    token_count = len(model.responses[0].split(" "))
    final = TokenUsage(
        input_tokens=model.usage["input_tokens"],
        output_tokens=model.usage["output_tokens"],
        total_tokens=model.usage["total_tokens"],
        source="on_llm_end",
    )
    return [None] * token_count, final


def test_aggregator_refuses_to_answer_before_the_stream_closes(fake_model: FakeModel):
    chunks, _ = _ollama_shaped_stream(fake_model)
    agg = UsageAggregator()
    for chunk in chunks:
        agg.add_chunk(chunk)

    with pytest.raises(UsageReadTooEarly):
        _ = agg.usage


def test_usage_is_populated_after_aggregation(fake_model: FakeModel):
    chunks, final = _ollama_shaped_stream(fake_model)
    agg = UsageAggregator()
    for chunk in chunks:
        agg.add_chunk(chunk)
    agg.finish(final)

    assert agg.finished
    assert agg.chunk_count == len(chunks)
    usage = agg.usage
    assert usage is not None
    assert usage.is_populated
    assert usage.input_tokens == fake_model.usage["input_tokens"]
    assert usage.output_tokens == fake_model.usage["output_tokens"]


def test_naive_first_chunk_read_produces_the_false_negative(fake_model: FakeModel):
    """The negative control for failure mode 2 — the exact false negative Pitfall 8 names."""
    chunks, final = _ollama_shaped_stream(fake_model)

    assert naive_stream_usage(chunks) is None, "the wrong reader sees None..."

    agg = UsageAggregator()
    for chunk in chunks:
        agg.add_chunk(chunk)
    agg.finish(final)
    assert agg.usage is not None and agg.usage.is_populated, "...while the right one sees numbers"


def test_aggregator_recovers_usage_from_the_final_chunk_when_on_llm_end_is_silent(
    fake_model: FakeModel,
):
    """Some providers put usage on the last chunk and pass nothing to ``on_llm_end``."""
    chunks, final = _ollama_shaped_stream(fake_model)
    chunks[-1] = final

    agg = UsageAggregator()
    for chunk in chunks:
        agg.add_chunk(chunk)
    agg.finish(None)

    assert agg.usage is not None and agg.usage.is_populated


def test_a_genuinely_absent_usage_still_reads_as_none():
    """Vacuity guard: the aggregator must not manufacture numbers out of nothing.

    If this returned a populated record for an all-``None`` stream, SPIKE-05 would answer
    "yes, visible" no matter what Ollama did.
    """
    agg = UsageAggregator()
    for _ in range(4):
        agg.add_chunk(None)
    agg.finish(None)
    assert agg.usage is None


def test_half_populated_usage_is_not_counted_as_populated():
    """``is_populated`` requires both counts, matching langchain_ollama's own rule."""
    assert not TokenUsage(input_tokens=12, output_tokens=None).is_populated
    assert not TokenUsage(input_tokens=None, output_tokens=7).is_populated
    assert TokenUsage(input_tokens=12, output_tokens=7).is_populated


# --------------------------------------------------------------------------------------
# 3. The recorder itself keeps enough to answer the requirement
# --------------------------------------------------------------------------------------


def test_recorder_summary_reports_which_start_hooks_fired():
    trace = TraceRecorder()
    trace.record_prompt(["hi"], hook="on_chat_model_start", model_choice="ollama:qwen3.5:9b")
    trace.record_token("4")
    trace.record_token("8")
    trace.record_usage(TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5))

    summary = trace.summary()
    assert summary["prompt_hooks"] == ["on_chat_model_start"]
    assert summary["tokens"] == 2
    assert summary["usage_records_populated"] == 1
    assert trace.of_kind("prompt")[0].payload["model_choice"] == "ollama:qwen3.5:9b"
