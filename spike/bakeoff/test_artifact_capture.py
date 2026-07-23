"""SPIKE-06 Wave-0 unit tests: the structured half of a tool result must survive.

Framework-free — imports only ``bakeoff.port`` and the stdlib-only ``FakeTool`` from
``spike/conftest.py``, which returns a two-part ``(content, artifact)`` tuple precisely so
this file can falsify something. A double returning a bare string could not.

SPIKE-06 is the explicit falsification test for the whole agent-framework choice, so its
most dangerous outcome is not "no" — it is a **wrong** no. ``langchain_mcp_adapters``
converts every MCP tool into a ``StructuredTool`` with
``response_format="content_and_artifact"``; the structured payload rides in the artifact
half as ``MCPToolArtifact.structured_content``. A handler that records ``str(output)``
keeps the prose and drops the data, then reports that MCP results are invisible through
callbacks (RESEARCH Pitfall 9).

Every "the right capture works" assertion below is paired with the naive capture on the
same input, so the tests demonstrate the loss rather than assert its absence.
"""

from __future__ import annotations

from typing import Any

import pytest
from conftest import FakeTool

from bakeoff.port import (
    ToolInvocation,
    TraceRecorder,
    naive_tool_output,
    split_tool_output,
    structured_content_matches,
)

# --------------------------------------------------------------------------------------
# Shapes a tool result can arrive in. Each mirrors something real:
#   * ToolMessageLike  -> what langchain hands ``on_tool_end`` for a content_and_artifact tool
#   * the 2-tuple      -> what such a tool's own coroutine returns before langchain wraps it
#   * the mapping      -> the raw MCP CallToolResult / Pydantic AI hook shape
#   * the bare string  -> a plain non-MCP tool, where "no artifact" is the true answer
# --------------------------------------------------------------------------------------

STRUCTURED: dict[str, Any] = {
    "room": "kitchen",
    "temperature_c": 21.5,
    "devices": ["kettle", "lamp"],
}


class MCPToolArtifactLike:
    """Stands in for ``langchain_mcp_adapters.tools.MCPToolArtifact``."""

    def __init__(self, structured_content: dict[str, Any]) -> None:
        self.structured_content = structured_content


class ToolMessageLike:
    """Stands in for a ``langchain_core.messages.ToolMessage`` carrying an artifact."""

    def __init__(self, content: str, artifact: Any) -> None:
        self.content = content
        self.artifact = artifact


# --------------------------------------------------------------------------------------
# The tuple shape — exactly what conftest's FakeTool returns
# --------------------------------------------------------------------------------------


def test_fake_tool_returns_two_parts_so_this_file_can_falsify_something(fake_tool: FakeTool):
    output = fake_tool.invoke(room="kitchen")
    assert isinstance(output, tuple) and len(output) == 2


def test_split_retains_the_artifact_half_of_a_tuple(fake_tool: FakeTool):
    output = fake_tool.invoke(room="kitchen")
    result = split_tool_output(fake_tool.name, output)

    assert result.content == fake_tool.content
    assert result.artifact == fake_tool.artifact
    assert result.artifact_present is True


def test_naive_capture_loses_the_artifact_half_of_the_same_tuple(fake_tool: FakeTool):
    """The negative control. This is the bug that would sink SPIKE-06."""
    output = fake_tool.invoke(room="kitchen")
    result = naive_tool_output(fake_tool.name, output)

    assert result.artifact is None
    assert result.artifact_present is False
    assert result.structured_content is None
    # The structured payload is not merely unparsed — it is gone as data.
    assert not isinstance(result.content, tuple)


# --------------------------------------------------------------------------------------
# The langchain ToolMessage shape, with a real MCP-style structured payload
# --------------------------------------------------------------------------------------


def test_split_reaches_structured_content_inside_an_mcp_artifact():
    output = ToolMessageLike("kitchen is 21.5C", MCPToolArtifactLike(STRUCTURED))
    result = split_tool_output("room_status", output)

    assert result.content == "kitchen is 21.5C"
    assert result.artifact_present is True
    assert result.structured_content == STRUCTURED
    assert result.structured_content["devices"] == ["kettle", "lamp"]


def test_naive_capture_reduces_the_mcp_artifact_to_a_repr():
    output = ToolMessageLike("kitchen is 21.5C", MCPToolArtifactLike(STRUCTURED))
    result = naive_tool_output("room_status", output)

    assert result.structured_content is None
    assert isinstance(result.content, str)
    # ``str()`` of the message object does not even contain the numbers.
    assert "21.5" not in result.content


def test_split_handles_the_raw_mcp_mapping_shape():
    """The raw ``CallToolResult`` shape uses camelCase ``structuredContent``."""
    output = {"content": "kitchen is 21.5C", "structuredContent": STRUCTURED}
    result = split_tool_output("room_status", output)

    assert result.artifact_present is True
    assert result.structured_content == STRUCTURED
    assert result.content == "kitchen is 21.5C"


def test_split_handles_the_unwrapped_dict_pydantic_ai_delivers():
    """Regression test for a bug in the *instrument*, not in either framework.

    Pydantic AI's ``after_tool_execute`` hook hands over the MCP server's
    ``structuredContent`` as a plain ``dict`` — no content/artifact split at all. The first
    version of ``split_tool_output`` had no branch for that, so it reported
    ``artifact_present: false``, which reads as "the structured half was lost". The truth
    was the opposite: nothing was ever wrapped, so nothing could be lost.

    That would have been a false negative against Pydantic AI on SPIKE-06 — a framework
    rejected for a defect in the measuring device.
    """
    result = split_tool_output("room_status", dict(STRUCTURED))

    assert result.artifact_present is True
    assert result.structured_content == STRUCTURED


# --------------------------------------------------------------------------------------
# The check that carries SPIKE-06 once bare dicts count as structured
# --------------------------------------------------------------------------------------


def test_fixture_match_is_the_assertion_that_can_actually_fail():
    """``artifact_present`` is too weak on its own; the payload must equal what was sent."""
    wrapped = split_tool_output("room_status", ToolMessageLike("p", MCPToolArtifactLike(STRUCTURED)))
    unwrapped = split_tool_output("room_status", dict(STRUCTURED))

    # Both shapes, one assertion — which is what makes the two frameworks comparable.
    assert structured_content_matches(wrapped, STRUCTURED)
    assert structured_content_matches(unwrapped, STRUCTURED)


@pytest.mark.parametrize(
    ("mutation", "why"),
    [
        ({**STRUCTURED, "temperature_c": 99.9}, "a changed value"),
        ({k: v for k, v in STRUCTURED.items() if k != "devices"}, "a dropped field"),
        ({**STRUCTURED, "devices": "kettle, ceiling-lamp"}, "a stringified list"),
    ],
    ids=["changed-value", "dropped-field", "stringified-list"],
)
def test_fixture_match_rejects_a_payload_that_lost_something(mutation, why):
    """Negative controls: the check must notice each way a payload can be degraded."""
    degraded = split_tool_output("room_status", dict(mutation))
    assert not structured_content_matches(degraded, STRUCTURED), why


def test_fixture_match_rejects_the_naive_capture_of_both_shapes():
    for output in (ToolMessageLike("p", MCPToolArtifactLike(STRUCTURED)), dict(STRUCTURED)):
        assert not structured_content_matches(naive_tool_output("room_status", output), STRUCTURED)


# --------------------------------------------------------------------------------------
# Vacuity guards: the capture must not manufacture an artifact, and must not
# report one for a tool that genuinely has none.
# --------------------------------------------------------------------------------------


def test_a_plain_string_result_honestly_reports_no_artifact():
    result = split_tool_output("echo", "just prose")
    assert result.content == "just prose"
    assert result.artifact is None
    assert result.artifact_present is False
    assert result.structured_content is None


def test_an_explicitly_null_artifact_is_reported_as_absent_not_present():
    """``artifact_present`` must track reality, or SPIKE-06 answers yes for everything."""
    result = split_tool_output("room_status", ToolMessageLike("prose", None))
    assert result.artifact_present is False


def test_an_empty_structured_payload_is_still_present():
    """"Structured but empty" and "no structured half" are different findings."""
    result = split_tool_output("room_status", ToolMessageLike("prose", MCPToolArtifactLike({})))
    assert result.artifact_present is True
    assert result.structured_content == {}


# --------------------------------------------------------------------------------------
# End-to-end through the trace recorder — args AND results, which is the full requirement
# --------------------------------------------------------------------------------------


def test_recorder_keeps_both_halves_of_spike_06(fake_tool: FakeTool):
    trace = TraceRecorder()
    args = {"room": "kitchen"}

    trace.record_tool_start(ToolInvocation(name=fake_tool.name, args=args))
    output = ToolMessageLike("kitchen is 21.5C", MCPToolArtifactLike(STRUCTURED))
    trace.record_tool_end(split_tool_output(fake_tool.name, output))

    (invocation,) = trace.tool_invocations
    (result,) = trace.tool_results

    assert invocation.args == args, "SPIKE-06 requires the ARGS half"
    assert result.structured_content == STRUCTURED, "SPIKE-06 requires the RESULTS half"

    summary = trace.summary()
    assert summary["tool_invocations"] == 1
    assert summary["tool_results"] == 1
    assert summary["tool_results_with_artifact"] == 1


def test_a_naive_recorder_reports_zero_artifacts_on_the_same_run(fake_tool: FakeTool):
    """Same events, wrong capture: the summary that would have overturned Decision 1."""
    trace = TraceRecorder()
    trace.record_tool_start(ToolInvocation(name=fake_tool.name, args={"room": "kitchen"}))
    output = ToolMessageLike("kitchen is 21.5C", MCPToolArtifactLike(STRUCTURED))
    trace.record_tool_end(naive_tool_output(fake_tool.name, output))

    assert trace.summary()["tool_results_with_artifact"] == 0
