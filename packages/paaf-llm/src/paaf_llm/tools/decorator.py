# SPDX-License-Identifier: Apache-2.0
"""Custom @tool Python function decorator and reflection engine (TOOL-02)."""

from __future__ import annotations

import asyncio
import inspect
import re
from typing import Any, Callable, TypeVar, overload

from paaf_llm.ports import ToolSpec

F = TypeVar("F", bound=Callable[..., Any])


def _python_type_to_json_type(param_type: Any) -> str:
    """Map Python type annotation to JSON schema type string."""
    if param_type is inspect.Parameter.empty or param_type is Any:
        return "string"

    type_str = str(param_type).lower()
    if param_type in (int, "int"):
        return "integer"
    elif param_type in (float, "float"):
        return "number"
    elif param_type in (bool, "bool"):
        return "boolean"
    elif param_type in (str, "str"):
        return "string"
    elif param_type in (list, "list") or "list" in type_str:
        return "array"
    elif param_type in (dict, "dict") or "dict" in type_str:
        return "object"
    return "string"


def _parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    """Parse docstring to extract overall description and parameter descriptions."""
    if not doc:
        return "", {}

    lines = doc.strip().splitlines()
    summary_lines: list[str] = []
    param_descs: dict[str, str] = {}
    in_params_section = False
    current_param: str | None = None

    google_param_re = re.compile(r"^\s*([a-zA-Z_]\w*)\s*(?:\([^)]*\))?\s*:\s*(.*)$")
    sphinx_param_re = re.compile(r"^\s*:param\s+([a-zA-Z_]\w*)\s*:\s*(.*)$")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_params_section:
                current_param = None
            continue

        lower = stripped.lower()
        if lower in ("args:", "parameters:", "params:"):
            in_params_section = True
            current_param = None
            continue
        elif lower.endswith(":") and any(
            lower.startswith(k)
            for k in ("returns:", "raises:", "yields:", "example:")
        ):
            in_params_section = False
            current_param = None
            continue

        sphinx_match = sphinx_param_re.match(line)
        if sphinx_match:
            param_name, desc = sphinx_match.groups()
            param_descs[param_name] = desc.strip()
            current_param = param_name
            continue

        if in_params_section:
            google_match = google_param_re.match(line)
            if google_match:
                param_name, desc = google_match.groups()
                param_descs[param_name] = desc.strip()
                current_param = param_name
                continue
            elif current_param and param_descs.get(current_param):
                param_descs[current_param] += " " + stripped
                continue

        if not in_params_section and not param_descs:
            summary_lines.append(stripped)

    summary = " ".join(summary_lines)
    return summary, param_descs


def _build_tool_spec(
    func: Callable[..., Any],
    name: str | None = None,
    description: str | None = None,
) -> ToolSpec:
    """Reflect function signature and docstring into a PAAF ToolSpec."""
    func_name = name or func.__name__
    doc_summary, param_descs = _parse_docstring(func.__doc__)
    func_desc = description or doc_summary or f"Execute {func_name}"

    sig = inspect.signature(func)
    properties: dict[str, object] = {}
    required: list[str] = []

    for p_name, param in sig.parameters.items():
        if p_name in ("self", "cls"):
            continue

        p_type = _python_type_to_json_type(param.annotation)
        p_info: dict[str, object] = {"type": p_type}

        if p_name in param_descs:
            p_info["description"] = param_descs[p_name]

        if param.default is inspect.Parameter.empty:
            required.append(p_name)
        else:
            p_info["default"] = param.default

        properties[p_name] = p_info

    parameters: dict[str, object] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        parameters["required"] = required

    return ToolSpec(name=func_name, description=func_desc, parameters=parameters)


@overload
def tool(func: F) -> F:
    ...


@overload
def tool(
    *,
    name: str | None = None,
    description: str | None = None,
    tier: str | None = None,
) -> Callable[[F], F]:
    ...


def tool(
    func: F | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    tier: str | None = None,
) -> Any:
    """Decorator to convert a Python function into a PAAF ToolSpec."""

    def decorator(fn: F) -> F:
        spec = _build_tool_spec(fn, name=name, description=description)
        is_async = inspect.iscoroutinefunction(fn)

        setattr(fn, "__tool_spec__", spec)
        setattr(fn, "__tool_func__", fn)
        setattr(fn, "__tool_is_async__", is_async)
        setattr(fn, "__tool_tier__", tier or "default")

        return fn

    if func is not None:
        return decorator(func)
    return decorator


async def execute_tool_func(func: Callable[..., Any], **kwargs: Any) -> Any:
    """Execute a decorated or raw tool function, offloading sync calls to thread pool."""
    target_func = getattr(func, "__tool_func__", func)
    if inspect.iscoroutinefunction(target_func):
        return await target_func(**kwargs)
    else:
        return await asyncio.to_thread(target_func, **kwargs)
