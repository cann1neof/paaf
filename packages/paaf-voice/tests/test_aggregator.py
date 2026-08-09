# SPDX-License-Identifier: Apache-2.0
"""Tests for SentenceAggregator."""

import pytest
from paaf_voice.aggregator import AggregatorConfig, SentenceAggregator


@pytest.mark.asyncio
async def test_latin_sentence_boundaries():
    aggregator = SentenceAggregator()

    async def token_gen():
        for t in ["Hello ", "world", ". ", "How ", "are ", "you", "?"]:
            yield t

    chunks = [c async for c in aggregator.aggregate_stream(token_gen())]
    assert len(chunks) == 2
    assert chunks[0] == "Hello world."
    assert chunks[1] == "How are you?"


@pytest.mark.asyncio
async def test_cyrillic_sentence_boundaries():
    aggregator = SentenceAggregator()

    async def token_gen():
        for t in ["Привет ", "мир", ". ", "Как ", "дела", "?"]:
            yield t

    chunks = [c async for c in aggregator.aggregate_stream(token_gen())]
    assert len(chunks) == 2
    assert chunks[0] == "Привет мир."
    assert chunks[1] == "Как дела?"


@pytest.mark.asyncio
async def test_hebrew_sof_pasuq_boundary():
    aggregator = SentenceAggregator()

    async def token_gen():
        for t in ["שלום ", "עולם", "׃ ", "מה ", "שלומך", "?"]:
            yield t

    chunks = [c async for c in aggregator.aggregate_stream(token_gen())]
    assert len(chunks) == 2
    assert chunks[0] == "שלום עולם׃"
    assert chunks[1] == "מה שלומך?"


@pytest.mark.asyncio
async def test_cjk_sentence_boundaries():
    aggregator = SentenceAggregator()

    async def token_gen():
        for t in ["こんにちは", "。", "元気", "ですか", "？"]:
            yield t

    chunks = [c async for c in aggregator.aggregate_stream(token_gen())]
    assert len(chunks) == 2
    assert chunks[0] == "こんにちは。"
    assert chunks[1] == "元気ですか？"


@pytest.mark.asyncio
async def test_decimal_protection():
    aggregator = SentenceAggregator()

    async def token_gen():
        for t in ["The ", "value ", "is ", "3", ".", "14", ". ", "Next ", "sentence", "."]:
            yield t

    chunks = [c async for c in aggregator.aggregate_stream(token_gen())]
    assert len(chunks) == 2
    assert chunks[0] == "The value is 3.14."
    assert chunks[1] == "Next sentence."


@pytest.mark.asyncio
async def test_abbreviation_protection():
    aggregator = SentenceAggregator()

    async def token_gen():
        for t in ["Dr", ". ", "Smith ", "is ", "here", ". ", "Welcome", "."]:
            yield t

    chunks = [c async for c in aggregator.aggregate_stream(token_gen())]
    assert len(chunks) == 2
    assert chunks[0] == "Dr. Smith is here."
    assert chunks[1] == "Welcome."


@pytest.mark.asyncio
async def test_mid_sentence_script_transition():
    aggregator = SentenceAggregator()

    async def token_gen():
        for t in ["Я ", "запускаю ", "Python ", "script", ". ", "Все ", "отлично", "."]:
            yield t

    chunks = [c async for c in aggregator.aggregate_stream(token_gen())]
    assert len(chunks) == 2
    assert chunks[0] == "Я запускаю Python script."
    assert chunks[1] == "Все отлично."


@pytest.mark.asyncio
async def test_dual_threshold_early_emission():
    config = AggregatorConfig(first_chunk_min_chars=20)
    aggregator = SentenceAggregator(config=config)

    # Chunk 1: "This is a long sentence header," (29 chars) has clause ',' -> emits chunk 1!
    # Chunk 2: " then we have another clause," -> ignores ',' because emitted_first_chunk is True!
    # " and ends here." -> emits on '.'!
    tokens = [
        "This ", "is ", "a ", "long ", "sentence ", "header", ", ",
        "then ", "we ", "have ", "another ", "clause", ", ",
        "and ", "ends ", "here", "."
    ]

    async def token_gen():
        for t in tokens:
            yield t

    chunks = [c async for c in aggregator.aggregate_stream(token_gen())]
    assert len(chunks) == 2
    assert chunks[0] == "This is a long sentence header,"
    assert chunks[1] == "then we have another clause, and ends here."


@pytest.mark.asyncio
async def test_token_count_safety_fallback():
    config = AggregatorConfig(first_chunk_min_chars=100, max_first_chunk_tokens=5)
    aggregator = SentenceAggregator(config=config)

    # 5 tokens without punctuation -> triggers fallback
    tokens = ["One ", "two ", "three ", "four ", "five "]

    async def token_gen():
        for t in tokens:
            yield t

    chunks = [c async for c in aggregator.aggregate_stream(token_gen())]
    assert len(chunks) == 1
    assert chunks[0] == "One two three four five"
