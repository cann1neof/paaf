# SPDX-License-Identifier: Apache-2.0
"""Tests for built-in system tools and peer graph prompt composition (TOOL-01, TOOL-08)."""

from __future__ import annotations

import paaf_llm.tools as tools_module
from paaf_llm.compose import PromptComposer
from paaf_llm.mesh import explainer_for, handoff_tools
from paaf_llm.ports import ToolSpec
from paaf_llm.profiles import ModelProfile


def test_peer_graph_injected_in_system_prompt() -> None:
    """Peer graph awareness is composed into the system prompt via mesh explainer."""
    agent = ModelProfile(provider="ollama", model="llama3", peers=("chef", "concierge"))
    profiles = {
        "chef": ModelProfile(provider="ollama", model="llama3", capabilities="Prepares gourmet meals"),
        "concierge": ModelProfile(provider="ollama", model="llama3", capabilities="Handles reservations"),
    }
    explainer = explainer_for("host", agent, profiles)
    assert "chef" in explainer
    assert "Prepares gourmet meals" in explainer
    assert "concierge" in explainer

    composer = PromptComposer()
    prompt = composer.compose("Base prompt", [], [("mesh:explainer", explainer)])
    assert "chef" in prompt
    assert "concierge" in prompt


def test_no_list_peers_tool_exists() -> None:
    """Confirm list_peers tool is explicitly forbidden and absent across builtins and mesh."""
    # Check paaf_llm.tools exports
    assert not hasattr(tools_module, "list_peers")
    for spec in tools_module.BUILTIN_TOOL_SPECS:
        assert spec.name != "list_peers"

    # Check handoff tools generated for peers
    agent = ModelProfile(provider="ollama", model="llama3", peers=("peer_a", "peer_b"))
    profiles = {
        "peer_a": ModelProfile(provider="ollama", model="llama3"),
        "peer_b": ModelProfile(provider="ollama", model="llama3"),
    }
    specs = handoff_tools("host", agent, profiles)
    tool_names = [s.name for s in specs]
    assert "list_peers" not in tool_names
    assert "transfer_to_peer_a" in tool_names
    assert "transfer_to_peer_b" in tool_names


def test_builtin_tool_specs_exported() -> None:
    """Always-on built-in tools (handoff, observer tools, datetime, history) are exported as ToolSpecs."""
    assert isinstance(tools_module.DATETIME_LOOKUP_SPEC, ToolSpec)
    assert tools_module.DATETIME_LOOKUP_SPEC.name == "date_time_lookup"

    assert isinstance(tools_module.HISTORY_LOOKUP_SPEC, ToolSpec)
    assert tools_module.HISTORY_LOOKUP_SPEC.name == "history_lookup"

    assert isinstance(tools_module.APPROVE_HANDOFF_SPEC, ToolSpec)
    assert tools_module.APPROVE_HANDOFF_SPEC.name == "approve_handoff"

    assert isinstance(tools_module.VETO_HANDOFF_SPEC, ToolSpec)
    assert tools_module.VETO_HANDOFF_SPEC.name == "veto_handoff"

    assert isinstance(tools_module.REROUTE_HANDOFF_SPEC, ToolSpec)
    assert tools_module.REROUTE_HANDOFF_SPEC.name == "reroute_handoff"

    handoff_spec = tools_module.get_handoff_tool_spec("chef")
    assert isinstance(handoff_spec, ToolSpec)
    assert handoff_spec.name == "transfer_to_chef"
