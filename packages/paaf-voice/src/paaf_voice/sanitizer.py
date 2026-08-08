# SPDX-License-Identifier: Apache-2.0
"""TTS Sanitizer for cleaning LLM streaming output before synthesis."""

import re
import unicodedata

# Compiled regex patterns for text sanitization
FENCED_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
RAW_URL_RE = re.compile(r"https?://\S+")
MARKDOWN_HEADING_RE = re.compile(r"^#+\s*", re.MULTILINE)
INLINE_BACKTICK_RE = re.compile(r"`")
MARKDOWN_FORMATTING_RE = re.compile(r"(\*\*|\*|__|~+)")
MULTIPLE_WHITESPACE_RE = re.compile(r"\s+")


class TTSSanitizer:
    """Sanitizer for cleaning LLM output prior to Text-To-Speech synthesis."""

    @staticmethod
    def sanitize(text: str) -> str:
        """Clean markdown formatting, code blocks, URLs, and emojis from text."""
        if not text:
            return ""

        # 1. Strip fenced code blocks
        clean = FENCED_CODE_BLOCK_RE.sub("", text)

        # 2. Convert markdown links [text](url) -> text
        clean = MARKDOWN_LINK_RE.sub(r"\1", clean)

        # 3. Strip raw URLs (http://, https://)
        clean = RAW_URL_RE.sub("", clean)

        # 4. Remove markdown headings
        clean = MARKDOWN_HEADING_RE.sub("", clean)

        # 5. Remove inline backticks
        clean = INLINE_BACKTICK_RE.sub("", clean)

        # 6. Remove bold/italic/strikethrough markers (*, **, _, __, ~)
        clean = MARKDOWN_FORMATTING_RE.sub("", clean)

        # 7. Strip Emojis (Symbol, other 'So' category)
        clean = "".join(
            char for char in clean if unicodedata.category(char) != "So"
        )

        # 8. Normalize whitespace
        clean = MULTIPLE_WHITESPACE_RE.sub(" ", clean).strip()

        return clean
