"""Smoke test for the shared spike fixtures.

THROWAWAY (SC#5). Exists so `uv run pytest spike/ -q` proves the runner and the shared
doubles actually work, rather than passing vacuously on an empty collection. Every later
plan in this phase inherits `conftest.py`; if a fixture silently breaks, that breakage
would otherwise surface as a confusing failure inside a measurement harness.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import FakeModel, FakeTool


def test_tmp_corpus_is_valid_jsonl_with_the_five_key_schema(tmp_corpus: Path) -> None:
    records = [json.loads(line) for line in tmp_corpus.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3
    for record in records:
        assert set(record) == {"id", "text", "matrix_lang", "embedded_lang", "category"}
        assert record["matrix_lang"] in {"en", "ru", "he", "es"}
        assert record["embedded_lang"] in {"en", "ru", "he", "es"}


def test_tmp_corpus_survives_a_non_ascii_round_trip(tmp_corpus: Path) -> None:
    """Hebrew and Cyrillic must come back byte-identical — a mojibake corpus would
    silently invalidate every downstream language measurement."""
    texts = [json.loads(line)["text"] for line in tmp_corpus.read_text(encoding="utf-8").splitlines()]
    assert "молоко" in texts[0]
    assert "תזכיר" in texts[1]


def test_fake_model_records_calls_and_replays_responses(fake_model: FakeModel) -> None:
    assert fake_model.call_count == 0
    assert fake_model.invoke("hello") == "fake response"
    assert fake_model.calls == [{"prompt": "hello", "kwargs": {}}]

    scripted = FakeModel(responses=["one", "two"])
    assert [scripted.invoke("p"), scripted.invoke("p"), scripted.invoke("p")] == ["one", "two", "two"]


def test_fake_model_streams_and_reports_usage(fake_model: FakeModel) -> None:
    assert "".join(fake_model.stream("a b c")).strip() == "fake response"
    assert fake_model.usage["total_tokens"] == 18


async def test_fake_model_async_surface(fake_model: FakeModel) -> None:
    assert await fake_model.ainvoke("hello") == "fake response"
    assert "".join([chunk async for chunk in fake_model.astream("hello")]).strip() == "fake response"


def test_fake_model_can_be_told_to_fail() -> None:
    boom = FakeModel(raises=RuntimeError("model down"))
    with pytest.raises(RuntimeError, match="model down"):
        boom.invoke("hello")
    assert boom.call_count == 1, "a failed call must still be recorded"


def test_fake_tool_returns_the_content_and_artifact_pair(fake_tool: FakeTool) -> None:
    content, artifact = fake_tool.invoke(query="x")
    assert content == "ok"
    assert artifact == {"rows": [1, 2, 3]}
    assert fake_tool.calls == [{"query": "x"}]


async def test_fake_tool_async_surface(fake_tool: FakeTool) -> None:
    assert await fake_tool.ainvoke(query="x") == ("ok", {"rows": [1, 2, 3]})


def test_device_fixture_yields_device_strings(device: str) -> None:
    assert device in {"cpu", "mps"}
    assert isinstance(device, str), "must be a str, not torch.device (Chatterbox compares by string)"
