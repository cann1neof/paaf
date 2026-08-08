# SPDX-License-Identifier: Apache-2.0
"""CI verification test: prompt injection non-defensive governance (TOOL-07, PERS-05, D-18).

Asserts 100% absence of hidden defensive prompt instructions across all composed system prompts,
mesh explainer fragments, observer prompts, and built-in system tools. PAAF's sole defense
against prompt injection via tool outputs is explicit permission tiers (observe, act, confirm).
"""

from __future__ import annotations

from paaf_llm.compose import PromptComposer
from paaf_llm.mesh import base_prompt_for, mesh_fragments_for
from paaf_llm.profiles import LlmConfig, ModelProfile
from paaf_llm.tools import BUILTIN_TOOL_SPECS

FORBIDDEN_DEFENSIVE_PHRASES = [
    "ignore previous instructions",
    "prompt injection",
    "do not follow commands in tool output",
    "untrusted input from tool",
    "sanitized output",
    "do not execute commands",
    "disregard instructions",
]


def test_no_hidden_defensive_phrases_in_system_prompts() -> None:
    """Verify system prompts across all profiles contain ZERO hidden defensive instructions."""
    config = LlmConfig(
        active_profile="assistant",
        profiles={
            "assistant": ModelProfile(
                provider="ollama",
                model="llama3",
                system_prompt="You are a helpful assistant.",
            ),
            "observer": ModelProfile(
                provider="ollama",
                model="llama3",
                system_prompt="You observe safety and policy.",
            ),
        },
    )

    composer = PromptComposer()

    for p_name, profile in config.profiles.items():
        base = base_prompt_for(profile, config)
        mesh_frags = mesh_fragments_for(p_name, profile, config)
        composed = composer.compose(base, [], mesh_frags).lower()

        for phrase in FORBIDDEN_DEFENSIVE_PHRASES:
            assert (
                phrase not in composed
            ), f"Forbidden defensive phrase '{phrase}' found in prompt for profile '{p_name}'"


def test_no_hidden_defensive_phrases_in_builtin_tool_specs() -> None:
    """Verify built-in tool docstrings and descriptions contain zero defensive phrases."""
    for spec in BUILTIN_TOOL_SPECS:
        desc = spec.description.lower()
        for phrase in FORBIDDEN_DEFENSIVE_PHRASES:
            assert (
                phrase not in desc
            ), f"Forbidden defensive phrase '{phrase}' found in tool spec '{spec.name}'"
