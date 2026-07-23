"""Shared fixtures for the Phase 1 spike quarantine.

THROWAWAY. Nothing in ``spike/`` ships (roadmap SC#5) and neither this code nor its
signatures carry forward (D-18). Phase 3 designs its port fresh from the findings.

Deliberate constraint: **this module imports nothing but the standard library and
pytest.** No torch, no chatterbox, no faster-whisper, no langchain, no pydantic-ai. The
voice half and the bake-off half of this phase live in two separate venvs (chatterbox
hard-pins ``torch==2.6.0`` / ``numpy<2``), so a conftest that reached for either would
break collection in the other. The doubles below are plain in-memory objects for exactly
that reason.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# The six D-02 failure-grid categories. The authoritative definition (and the real
# ~20-sentence corpus) lands in plan 01-02 under
# .planning/phases/01-spike-gate/corpus/corpus.jsonl; this copy exists only so the
# throwaway fixture below is schema-identical to the surviving one.
_D02_CATEGORIES = (
    "single-foreign-noun-in-english-frame",
    "mid-clause-switch",
    "hebrew-rtl-adjacent-to-latin-digits",
    "proper-nouns",
    "numbers-and-units",
    "same-script-russian-english-pair",
)

_CORPUS_KEYS = ("id", "text", "matrix_lang", "embedded_lang", "category")


# --------------------------------------------------------------------------------------
# Corpus
# --------------------------------------------------------------------------------------


@pytest.fixture
def tmp_corpus(tmp_path: Path) -> Path:
    """Write a tiny throwaway ``corpus.jsonl`` under ``tmp_path`` and return its path.

    Three records, using the exact five-key schema of the surviving corpus fixture
    (``id``, ``text``, ``matrix_lang``, ``embedded_lang``, ``category``) so that render,
    transcribe and round-trip harnesses can be exercised without touching — or waiting
    on — the real ~20-sentence grid. This is *not* a substitute for the real corpus: it
    covers three of the six D-02 categories and makes no D-03 matrix-variation promise.
    """
    records: list[dict[str, str]] = [
        {
            "id": "tmp-001",
            "text": "I need to buy молоко on the way home.",
            "matrix_lang": "en",
            "embedded_lang": "ru",
            "category": "single-foreign-noun-in-english-frame",
        },
        {
            "id": "tmp-002",
            "text": "תזכיר לי בשעה 7:30 to call the clinic.",
            "matrix_lang": "he",
            "embedded_lang": "en",
            "category": "hebrew-rtl-adjacent-to-latin-digits",
        },
        {
            "id": "tmp-003",
            "text": "Pon el timer a 15 minutes, por favor.",
            "matrix_lang": "es",
            "embedded_lang": "en",
            "category": "numbers-and-units",
        },
    ]
    assert all(set(r) == set(_CORPUS_KEYS) for r in records)
    assert all(r["category"] in _D02_CATEGORIES for r in records)

    path = tmp_path / "corpus.jsonl"
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------------------
# Framework-free doubles
# --------------------------------------------------------------------------------------


class FakeModel:
    """In-memory stand-in for a chat model. Imports no agent framework.

    Records every call so a trace handler under test can be checked against ground
    truth (SPIKE-05), replays a scripted list of replies, and reports token usage
    only once — after the final chunk — which mirrors the real aggregation behaviour
    the trace handler must not read too early.
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        usage: dict[str, int] | None = None,
        raises: BaseException | None = None,
    ) -> None:
        self.responses: list[str] = list(responses) if responses else ["fake response"]
        self.usage: dict[str, int] = dict(
            usage or {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
        )
        self.raises = raises
        self.calls: list[dict[str, Any]] = []
        self._n = 0

    # -- helpers -----------------------------------------------------------------
    def _next(self, prompt: Any, kwargs: dict[str, Any]) -> str:
        self.calls.append({"prompt": prompt, "kwargs": dict(kwargs)})
        if self.raises is not None:
            raise self.raises
        reply = self.responses[min(self._n, len(self.responses) - 1)]
        self._n += 1
        return reply

    @property
    def call_count(self) -> int:
        return len(self.calls)

    # -- sync --------------------------------------------------------------------
    def invoke(self, prompt: Any, **kwargs: Any) -> str:
        return self._next(prompt, kwargs)

    def stream(self, prompt: Any, **kwargs: Any):
        for token in self._next(prompt, kwargs).split(" "):
            yield token + " "

    # -- async -------------------------------------------------------------------
    async def ainvoke(self, prompt: Any, **kwargs: Any) -> str:
        return self._next(prompt, kwargs)

    async def astream(self, prompt: Any, **kwargs: Any):
        for token in self._next(prompt, kwargs).split(" "):
            yield token + " "


class FakeTool:
    """In-memory stand-in for a tool. Imports no agent framework.

    Returns the two-part ``(content, artifact)`` shape on purpose: SPIKE-06's whole
    question is whether the *artifact* half survives the port boundary, so a double
    that returned a bare string could not falsify anything.
    """

    def __init__(
        self,
        name: str = "fake_tool",
        content: Any = "ok",
        artifact: Any = None,
        raises: BaseException | None = None,
    ) -> None:
        self.name = name
        self.description = f"Throwaway spike double named {name!r}."
        self.content = content
        self.artifact = artifact if artifact is not None else {"rows": [1, 2, 3]}
        self.raises = raises
        self.calls: list[dict[str, Any]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def __call__(self, **kwargs: Any) -> tuple[Any, Any]:
        return self.invoke(**kwargs)

    def invoke(self, **kwargs: Any) -> tuple[Any, Any]:
        self.calls.append(dict(kwargs))
        if self.raises is not None:
            raise self.raises
        return self.content, self.artifact

    async def ainvoke(self, **kwargs: Any) -> tuple[Any, Any]:
        return self.invoke(**kwargs)


@pytest.fixture
def fake_model() -> FakeModel:
    """A fresh :class:`FakeModel`. Reconfigure via its constructor when a test needs
    scripted replies, a specific usage dict, or an induced failure."""
    return FakeModel()


@pytest.fixture
def fake_tool() -> FakeTool:
    """A fresh :class:`FakeTool` returning ``(content, artifact)``."""
    return FakeTool()


# --------------------------------------------------------------------------------------
# Device
# --------------------------------------------------------------------------------------


@pytest.fixture(params=["cpu", "mps"])
def device(request: pytest.FixtureRequest) -> str:
    """Device under test, as a **string** — ``"cpu"`` or ``"mps"``.

    A string, never ``torch.device``: Chatterbox's ``from_pretrained`` compares
    ``device == "mps"`` by string equality despite its ``torch.device`` type hint, so
    passing ``torch.device("mps")`` silently skips its availability check.

    D-11 scopes SPIKE-03 to Mac MPS and Mac CPU only. MPS on Chatterbox is
    documented-unreliable; a test that fails on ``"mps"`` is recording a **valid
    measurement**, not hitting a blocker — handle it as data, do not skip it away
    without recording why.
    """
    return request.param
