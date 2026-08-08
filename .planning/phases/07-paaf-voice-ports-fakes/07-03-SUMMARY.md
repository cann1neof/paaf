---
phase: "07"
plan: "03"
subsystem: "voice"
tags:
  - "sanitizer"
  - "aggregator"
  - "tts-preprocessing"
  - "multilingual"
requires:
  - "07-01-PLAN.md"
provides:
  - "paaf_voice.sanitizer.TTSSanitizer"
  - "paaf_voice.aggregator.SentenceAggregator"
  - "paaf_voice.aggregator.AggregatorConfig"
affects:
  - "packages/paaf-voice"
tech-stack:
  added: []
  patterns:
    - "Streaming text aggregation with dual character thresholds and punctuation boundary rules"
    - "ReDoS-safe regex preprocessing for LLM output sanitization"
key-files:
  created:
    - "packages/paaf-voice/src/paaf_voice/sanitizer.py"
    - "packages/paaf-voice/src/paaf_voice/aggregator.py"
    - "packages/paaf-voice/tests/test_sanitizer.py"
    - "packages/paaf-voice/tests/test_aggregator.py"
  modified:
    - "packages/paaf-voice/src/paaf_voice/__init__.py"
key-decisions:
  - "Zero external NLTK dependencies for multilingual sentence aggregation (stdlib unicode + regex)"
  - "TTSSanitizer automatically invoked during SentenceAggregator chunk emission"
requirements-completed:
  - "VOICE-06"
duration: "5 min"
completed: "2026-08-08"
coverage:
  - deliverable: "TTSSanitizer for cleaning LLM text prior to synthesis"
    verification:
      - kind: "command"
        ref: "uv run pytest packages/paaf-voice/tests/test_sanitizer.py"
        status: "pass"
    human_judgment: false
  - deliverable: "SentenceAggregator for multilingual LLM token stream sentence chunking"
    verification:
      - kind: "command"
        ref: "uv run pytest packages/paaf-voice/tests/test_aggregator.py"
        status: "pass"
    human_judgment: false
---

# Phase 07 Plan 03: Sentence Aggregator & TTS Sanitizer Summary

Delivered `TTSSanitizer` and `SentenceAggregator` for cleaning and sentence-chunking LLM streaming text for voice synthesis.

## Key Accomplishments

1. **TTSSanitizer**:
   - Strips markdown code blocks, backticks, headings, URLs, formatting markers, and `So` category emojis.
   - Converts markdown links `[text](url)` to anchor text (`text`).
   - Normalizes whitespace to prevent stuttering in TTS engines.

2. **SentenceAggregator**:
   - Aggregates streaming tokens into sentence chunks across Latin, Cyrillic, Hebrew (Sof Pasuq `׃`), and CJK (`。`, `！`, `？`) scripts.
   - Implemented protection rules for decimals (`3.14`) and abbreviations (`Dr.`, `Mr.`, `e.g.`).
   - Enforces dual character thresholds (20 chars + clause for chunk 1 vs sentence terminator for subsequent chunks) and 15-token safety fallback.
   - Automatically cleans emitted chunks with `TTSSanitizer`.

## Verification

- `uv run pytest packages/paaf-voice/tests/test_sanitizer.py` (5 passed)
- `uv run pytest packages/paaf-voice/tests/test_aggregator.py` (9 passed)

## Self-Check: PASSED
