# SPDX-License-Identifier: Apache-2.0
"""Tool autodiscovery loader for PAAF skills (SKILL-01)."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

from paaf_core.config.schema import PermissionTier
from paaf_llm.ports import ToolSpec
from paaf_llm.registry import ToolRegistry


def load_skill_tools(skill_dir: Path, skill_name: str, registry: ToolRegistry) -> None:
    """Scan skill directory for *.py files, dynamically import them, and register @tool decorated functions."""
    if not skill_dir.exists() or not skill_dir.is_dir():
        raise FileNotFoundError(f"Skill directory does not exist: {skill_dir}")

    py_files = sorted([p for p in skill_dir.glob("*.py") if not p.name.startswith("_")])

    for py_file in py_files:
        module_name = f"paaf_skill_{skill_name}_{py_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            continue

        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            raise RuntimeError(f"Failed to load skill module {py_file}: {e}") from e

        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if hasattr(attr, "__tool_spec__"):
                tool_spec: ToolSpec = getattr(attr, "__tool_spec__")
                tool_func = getattr(attr, "__tool_func__", attr)
                raw_tier = getattr(attr, "__tool_tier__", "act")
                try:
                    default_tier = PermissionTier(raw_tier)
                except ValueError:
                    default_tier = PermissionTier.ACT

                source = f"skill:{skill_name}"
                registry.register(
                    spec=tool_spec,
                    source=source,
                    func=tool_func,
                    default_tier=default_tier,
                )
