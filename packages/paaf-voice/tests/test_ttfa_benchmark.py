# SPDX-License-Identifier: Apache-2.0
"""Empirical TTFA (Time-To-First-Audio) benchmark test suite."""

import pytest

from paaf_voice.aggregator import AggregatorConfig, SentenceAggregator


@pytest.mark.asyncio
async def test_ttfa_first_chunk_latency_benchmark():
    tokens = [
        "Hello ", "my ", "dear ", "friend, ", "I ", "am ", "ready ", "to ",
        "assist ", "you. ", "How ", "can ", "I ", "help?"
    ]

    # Strategy 1: PAAF Short dual threshold strategy (20 chars + clause)
    short_config = AggregatorConfig(first_chunk_min_chars=20)
    short_aggregator = SentenceAggregator(config=short_config)

    short_first_index: int | None = None
    short_chunks: list[str] = []

    for idx, token in enumerate(tokens):
        emitted = short_aggregator.add_token(token)
        if emitted and short_first_index is None:
            short_first_index = idx
        short_chunks.extend(emitted)

    short_chunks.extend(short_aggregator.flush())

    # Strategy 2: Single long threshold baseline strategy (60 chars min)
    long_config = AggregatorConfig(first_chunk_min_chars=60)
    long_aggregator = SentenceAggregator(config=long_config)

    long_first_index: int | None = None
    long_chunks: list[str] = []

    for idx, token in enumerate(tokens):
        emitted = long_aggregator.add_token(token)
        if emitted and long_first_index is None:
            long_first_index = idx
        long_chunks.extend(emitted)

    long_chunks.extend(long_aggregator.flush())

    # Assertions
    assert short_first_index is not None
    assert long_first_index is not None

    # Dual threshold strategy emits first chunk significantly earlier in token sequence
    assert short_first_index < long_first_index

    # Short strategy emits first clause at "Hello my dear friend," (index 3, token "friend, ")
    assert short_first_index == 3
    assert short_chunks[0] == "Hello my dear friend,"

    # Total aggregated text output matches across both strategies
    full_text_short = " ".join(short_chunks)
    full_text_long = " ".join(long_chunks)
    assert full_text_short == full_text_long
