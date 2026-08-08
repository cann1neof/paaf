# SPDX-License-Identifier: Apache-2.0
"""Tests for TTSSanitizer."""

from paaf_voice.sanitizer import TTSSanitizer


def test_sanitize_fenced_code_block():
    raw = "Here is code ```python\nprint('hi')\n``` end"
    clean = TTSSanitizer.sanitize(raw)
    assert clean == "Here is code end"


def test_sanitize_markdown_links():
    raw = "Click [here](https://paaf.ai) now to visit [PAAF](https://paaf.ai/docs)."
    clean = TTSSanitizer.sanitize(raw)
    assert clean == "Click here now to visit PAAF."


def test_sanitize_raw_urls():
    raw = "Visit https://paaf.ai today for information."
    clean = TTSSanitizer.sanitize(raw)
    assert clean == "Visit today for information."


def test_sanitize_emojis():
    raw = "Hello world 👋! 😊 Have a nice day 🚀"
    clean = TTSSanitizer.sanitize(raw)
    assert clean == "Hello world ! Have a nice day"


def test_sanitize_formatting_and_headings():
    raw = "# Header\n**bold** and *italic* and `code_inline` text"
    clean = TTSSanitizer.sanitize(raw)
    assert clean == "Header bold and italic and code_inline text"
