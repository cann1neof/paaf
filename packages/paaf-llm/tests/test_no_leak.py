# SPDX-License-Identifier: Apache-2.0
"""MODEL-08 / T-03-11: the public surface is PAAF-typed and framework-free.

CLAUDE.md's founding constraint — "the public API must never leak the underlying
agent framework's types, so it stays swappable" — is only worth anything if it is
mechanical. This module makes it so, in two independent ways:

1. **No framework type is nameable.** :func:`test_public_signatures_are_paaf_typed`
   walks every name in ``paaf_llm.__all__``, resolves every annotation those
   objects declare, and fails if any annotation resolves to a module outside the
   standard library, ``paaf_llm``, or ``paaf_core``. A leak therefore fails the
   build rather than surviving as a review comment nobody makes.

2. **No framework module is even loaded.** :func:`test_import_paaf_llm_needs_no_framework`
   asserts ``import paaf_llm`` pulls in no ``langchain*``/``langgraph*`` module,
   in-process AND in a pristine subprocess. This is the runtime half of SC#1: if
   the adapter package were imported eagerly (RESEARCH Pitfall 4), the framework
   would become a hard dependency of the import and the shipped fake could never
   run framework-uninstalled.

Both halves carry a negative control (``..._detector_is_not_vacuous``) that
plants a fake framework type / module name and proves the detector reports it.
A check that cannot fail is not a check.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import typing
from collections.abc import Iterator, Mapping
from typing import Any, get_args, get_origin

import paaf_llm

#: Non-stdlib module roots a public annotation is allowed to name. ``paaf_core``
#: is here because ``ModelProfile.endpoint()`` legitimately returns a
#: ``paaf_core`` ``Endpoint`` — reusing the framework's own shared types is the
#: opposite of leaking a swappable dependency's types.
_ALLOWED_ROOTS = frozenset({"paaf_llm", "paaf_core"})

#: Names ``ports.py`` references under ``TYPE_CHECKING`` only, supplied here so
#: annotations resolve at runtime. ``HandoffRequest`` is the Phase-4 seam and has
#: no definition yet by design; stubbing it as ``object`` lets the walker reach
#: the annotations that DO matter instead of stopping at a ``NameError``.
_RESOLUTION_NS: dict[str, Any] = {
    "ModelProfile": paaf_llm.ModelProfile,
    "LlmConfig": paaf_llm.LlmConfig,
    "HandoffRequest": object,
}

_FRAMEWORK_PREFIXES = ("langchain", "langgraph")


def _module_roots(annotation: Any) -> set[str]:
    """Return the root module of every type named anywhere inside ``annotation``.

    Walks the full typing structure (``X | None``, ``Sequence[Message]``,
    ``list[tuple[str, str, str]]``, ``Literal[...]``) so a framework type cannot
    hide one layer down inside a generic parameter.
    """
    roots: set[str] = set()
    stack: list[Any] = [annotation]
    while stack:
        item = stack.pop()
        module = getattr(item, "__module__", None)
        if isinstance(module, str):
            roots.add(module.split(".")[0])
        origin = get_origin(item)
        if origin is not None:
            stack.append(origin)
        stack.extend(get_args(item))
    return roots


def _foreign_roots(annotation: Any) -> set[str]:
    """Return the roots in ``annotation`` that are neither stdlib nor PAAF."""
    return {
        root
        for root in _module_roots(annotation)
        if root not in _ALLOWED_ROOTS and root not in sys.stdlib_module_names
    }


def _resolved_hints(obj: Any) -> Mapping[str, Any]:
    module = sys.modules.get(getattr(obj, "__module__", ""), None)
    globalns = dict(getattr(module, "__dict__", {}))
    globalns.update(_RESOLUTION_NS)
    return typing.get_type_hints(obj, globalns=globalns)


def _public_annotations() -> Iterator[tuple[str, Any]]:
    """Yield ``(where, annotation)`` for everything the public surface declares.

    Only members DEFINED in ``paaf_llm`` are inspected. Inherited machinery (a
    Pydantic ``BaseModel``'s own ``model_dump``/``model_config``, for instance) is
    the base class's contract, not PAAF's public surface, and folding it in would
    make this test assert something it does not mean.
    """
    for name in paaf_llm.__all__:
        obj = getattr(paaf_llm, name)
        if not isinstance(obj, type):
            # Type aliases such as ``Role`` are annotations in their own right.
            yield f"paaf_llm.{name}", obj
            continue

        own_fields = set(vars(obj).get("__annotations__", {}))
        if own_fields:
            hints = _resolved_hints(obj)
            for field_name in own_fields:
                if field_name in hints:
                    yield f"{obj.__qualname__}.{field_name}", hints[field_name]

        for attr_name, member in vars(obj).items():
            if attr_name.startswith("_") or not inspect.isfunction(member):
                continue
            if not member.__module__.startswith("paaf_llm"):
                continue
            for param, hint in _resolved_hints(member).items():
                yield f"{obj.__qualname__}.{attr_name}({param})", hint


def test_public_signatures_are_paaf_typed() -> None:
    """No public annotation names a type from outside stdlib/paaf_llm/paaf_core."""
    leaks = {
        where: sorted(foreign)
        for where, annotation in _public_annotations()
        if (foreign := _foreign_roots(annotation))
    }
    assert leaks == {}, f"public API leaks non-PAAF types: {leaks}"


def test_signature_walker_is_not_vacuous() -> None:
    """Negative control: plant a framework type and prove the walker reports it."""

    class _FakeFrameworkMessage:
        pass

    _FakeFrameworkMessage.__module__ = "langchain_core.messages"

    assert _foreign_roots(_FakeFrameworkMessage) == {"langchain_core"}
    assert _foreign_roots(list[_FakeFrameworkMessage | None]) == {"langchain_core"}
    # ...and prove it does NOT cry wolf over the real public surface's shapes.
    assert _foreign_roots(list[tuple[str, str, str]]) == set()
    assert _foreign_roots(paaf_llm.Usage | None) == set()


def test_walker_actually_inspected_the_surface() -> None:
    """Positive control: the walker reaches real annotations, not an empty set."""
    inspected = {where for where, _ in _public_annotations()}
    assert "TurnResult.served_by" in inspected
    assert "ChatAdapter.stream(profile)" in inspected
    assert "FakeAdapter.program(fail)" in inspected


def _framework_modules(modules: Mapping[str, Any]) -> set[str]:
    return {name for name in modules if name.startswith(_FRAMEWORK_PREFIXES)}


def _framework_modules_after_a_clean_import() -> set[str]:
    """Return the framework modules a FRESH interpreter loads for ``import paaf_llm``.

    Measured in a child process rather than over this process's ``sys.modules``.
    The process-wide reading answers "has anything in this pytest session imported
    the framework?", which is a different question from "does importing
    ``paaf_llm`` import the framework?" — and it turns red as soon as any sibling
    legitimately imports it, which ``test_engine_adapter.py`` must do to test the
    real adapter at all. The child process is immune to test ordering and answers
    the question this module actually asks.

    The child reports its WHOLE module list and the filtering happens here, on
    purpose: ``_framework_modules`` stays the one detector, so the negative
    control that proves it bites still guards the assertion below.
    """
    probe = "import sys, paaf_llm; print('\\n'.join(sys.modules))"
    result = subprocess.run(
        [sys.executable, "-c", probe], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    loaded = dict.fromkeys(result.stdout.split())
    assert "paaf_llm" in loaded, "the probe did not import the package at all"
    return _framework_modules(loaded)


def test_import_paaf_llm_needs_no_framework() -> None:
    """``import paaf_llm`` must not drag in the agent framework (Pitfall 4)."""
    assert paaf_llm.FakeAdapter is not None  # the surface is fully importable
    assert _framework_modules_after_a_clean_import() == set()


def test_framework_module_detector_is_not_vacuous() -> None:
    """Negative control: the sys.modules probe reports a planted framework name."""
    planted = {"langchain_core.messages": object(), "paaf_llm.ports": object()}
    assert _framework_modules(planted) == {"langchain_core.messages"}


def test_import_paaf_llm_needs_no_framework_in_a_pristine_interpreter() -> None:
    """The same proof in a fresh process, immune to another test's imports."""
    probe = (
        "import sys; import paaf_llm; "
        "leaked = [m for m in sys.modules "
        "if m.startswith(('langchain', 'langgraph'))]; "
        "assert not leaked, leaked; "
        "assert paaf_llm.FakeAdapter and paaf_llm.ModelProfile"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
