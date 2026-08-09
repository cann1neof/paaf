# SPDX-License-Identifier: Apache-2.0
"""Multilingual sentence aggregator for LLM token streams."""

import re
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass

from paaf_voice.sanitizer import TTSSanitizer

# Sentences terminators across Latin, Cyrillic, Hebrew (Sof Pasuq ׃ U+05C3), and CJK scripts
SENTENCE_TERMINATORS = {".", "!", "?", "׃", "。", "！", "？"}
CLAUSE_PUNCTUATION = {",", ";", ":"}

# Abbreviation & decimal regex guards
ABBREVIATION_PATTERN = re.compile(
    r"\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|e\.g|i\.e|vs|etc|St|approx)\.$", re.IGNORECASE
)
DECIMAL_PATTERN = re.compile(r"\d+\.\d+$")


@dataclass(frozen=True, slots=True)
class AggregatorConfig:
    """Configuration thresholds for sentence aggregation."""

    first_chunk_min_chars: int = 20
    subsequent_min_chars: int = 60
    max_first_chunk_tokens: int = 15


class SentenceAggregator:
    """Aggregates streaming LLM tokens into natural sentences for TTS synthesis."""

    def __init__(self, config: AggregatorConfig | None = None) -> None:
        self.config = config or AggregatorConfig()
        self._buffer: str = ""
        self._token_count: int = 0
        self._emitted_first_chunk: bool = False

    def _is_protected_boundary(self, text: str) -> bool:
        """Check if trailing text is a protected abbreviation or decimal."""
        stripped = text.rstrip()
        # Full decimal e.g. 3.14 in middle of token
        if DECIMAL_PATTERN.search(stripped):
            return True
        # Decimal in progress e.g. "3." without trailing space
        if re.search(r"\d+\.$", stripped) and self._buffer.endswith("."):
            return True
        if ABBREVIATION_PATTERN.search(stripped):
            return True
        return False

    def add_token(self, token: str) -> list[str]:
        """Add a token to the buffer and return any completed sentence chunks."""
        self._buffer += token
        self._token_count += 1

        chunks: list[str] = []
        stripped = self._buffer.rstrip()
        if not stripped:
            return chunks

        last_char = stripped[-1]

        # Check protection rules
        if self._is_protected_boundary(stripped):
            return chunks

        should_emit = False

        if not self._emitted_first_chunk:
            # Chunk 1 early emission rules:
            # - >= first_chunk_min_chars AND (clause punctuation or sentence terminator)
            # - OR token_count >= max_first_chunk_tokens
            # - OR sentence terminator reached
            if (
                len(self._buffer) >= self.config.first_chunk_min_chars
                and (last_char in CLAUSE_PUNCTUATION or last_char in SENTENCE_TERMINATORS)
            ) or self._token_count >= self.config.max_first_chunk_tokens or last_char in SENTENCE_TERMINATORS:
                should_emit = True
        else:
            # Subsequent chunk rules:
            # - Ignore clause punctuation
            # - Emit on sentence terminator
            if last_char in SENTENCE_TERMINATORS:
                should_emit = True

        if should_emit:
            cleaned = TTSSanitizer.sanitize(self._buffer)
            if cleaned:
                chunks.append(cleaned)
                self._emitted_first_chunk = True
            self._buffer = ""
            self._token_count = 0

        return chunks

    def flush(self) -> list[str]:
        """Flush remaining buffer content as final chunk."""
        chunks: list[str] = []
        if self._buffer:
            cleaned = TTSSanitizer.sanitize(self._buffer)
            if cleaned:
                chunks.append(cleaned)
            self._buffer = ""
            self._token_count = 0
        return chunks

    async def aggregate_stream(
        self, token_stream: AsyncIterable[str]
    ) -> AsyncIterator[str]:
        """Consume an async stream of LLM tokens and yield sentence chunks."""
        async for token in token_stream:
            for chunk in self.add_token(token):
                yield chunk

        for chunk in self.flush():
            yield chunk
