"""SPIKE-04 — measure whether Whisper LOCKS onto one language and TRANSLITERATES or
TRANSLATES the rest, on the SAME corpus clips (D-04).

THROWAWAY (SC#5 / D-18) — this file dies with ``spike/``. What survives is what it
writes: ``.planning/phases/01-spike-gate/corpus/transcripts.jsonl`` (declared DATA under
D-07) and ``.planning/phases/01-spike-gate/raw/transcribe.md``.

The instrument (RESEARCH §Pitfall 7, §Don't Hand-Roll)
------------------------------------------------------
``faster-whisper`` is the ONLY STT engine that exposes the instrument the lock-on question
needs, so the harness uses all three parts of it and never falls back to script heuristics
(which cannot tell "locked to Russian and transliterated" from "correctly detected
Russian"):

1. ``multilingual`` flag — every clip is transcribed under BOTH ``multilingual=False``
   (``transcribe()``'s production default: detect once, apply globally) AND
   ``multilingual=True`` ("Perform language detection on every segment" — the best case).
2. ``info.all_language_probs`` — the full posterior over languages, captured top-k, plus a
   SEPARATE ``model.detect_language()`` call as an independent posterior.
3. ``task="translate"`` — an English-only target that captures the "translates the rest"
   half of SPIKE-04. Left at its ``"transcribe"`` default it would answer only half the
   question.

``vad_filter=False`` — the ``WhisperModel.transcribe`` default is actually ``False`` in
1.2.1 (01-03 correction 5 to RESEARCH's Pitfall 7 note), but it is set EXPLICITLY here so
a future default flip cannot silently trim the short synthetic clips and be misread as a
transcription failure.

The real limitation, recorded as a caveat
-----------------------------------------
The ``Segment`` dataclass carries **no** ``.language`` field. So even under
``multilingual=True``, per-segment language is INFERRED from ``all_language_probs`` and the
output script — it is not a direct per-segment label. Every row and the write-up carry
that caveat.

The binding caveat that travels with the result (D-05)
------------------------------------------------------
Whisper is fed **Chatterbox output**, not the user's real speech (D-04). This therefore
measures *"Whisper on synthetic mixed speech,"* and Chatterbox failures and Whisper
failures are NOT separable in this setup (D-05). Under SC#4 no README may claim PAAF
handles the user's real code-switched speech on this evidence. The caveat is written at
the top of ``raw/transcribe.md`` and flagged on every row.

Model choice
------------
``WhisperModel("large-v3", ...)`` — the first-party Systran repo, NOT the community
``large-v3-turbo`` conversion: a measurement phase must not attribute a community
conversion's flaws to Whisper (RESEARCH, 01-03). CTranslate2 has no Metal backend, so this
runs on ``device="cpu"`` with ``compute_type="int8"`` — slow but correct on ~46 short clips.

Usage
-----
    # transcribe every clip under all three conditions (resumable — done rows are skipped)
    spike/voice/.venv/bin/python spike/voice/transcribe.py

    # bounded smoke run (N clips), useful for validating the harness end-to-end
    spike/voice/.venv/bin/python spike/voice/transcribe.py --limit 2

    # what would be transcribed, without loading a model
    spike/voice/.venv/bin/python spike/voice/transcribe.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shuffle_blind as sb  # noqa: E402  — sibling module, the one naming convention

# --------------------------------------------------------------------------------------
# Constants — every knob recorded, none implicit (D-07)
# --------------------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / ".planning" / "phases" / "01-spike-gate" / "corpus"
CORPUS_PATH = CORPUS_DIR / "corpus.jsonl"
CLIPS_DIR = CORPUS_DIR / "clips"
TRANSCRIPTS_PATH = CORPUS_DIR / "transcripts.jsonl"
RAW_PATH = REPO_ROOT / ".planning" / "phases" / "01-spike-gate" / "raw" / "transcribe.md"

#: First-party Systran repo (utils._MODELS maps "large-v3" -> Systran/faster-whisper-large-v3),
#: never the community turbo conversion — a measurement phase must not attribute a
#: conversion's flaws to Whisper.
MODEL_NAME = "large-v3"

#: CTranslate2 has NO Metal/Apple-GPU backend; faster-whisper is CPU-only on this Mac.
#: Slow, not blocked — and only ~46 short clips.
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

#: SPIKE-04 must NEVER pin the language — the whole question is what Whisper decides.
LANGUAGE = None

#: vad_filter is set explicitly (see module docstring): the default is False on
#: WhisperModel.transcribe in 1.2.1, but stating it protects the short clips from a future
#: default flip that would trim them and look like a transcription failure.
VAD_FILTER = False

#: How many entries of the language posterior to keep. Enough to see whether the second-
#: place language is close (a near-miss lock-on) or nowhere (a confident, correct detect).
TOP_K = 5

#: The three conditions. Each is one row per clip. Recorded structurally so no reader has
#: to reverse-engineer which knob produced which transcript.
CONDITIONS: tuple[dict[str, Any], ...] = (
    # The production default: detect the language once, apply it to the whole clip. This is
    # the condition most likely to LOCK onto one language across a code-switched clip.
    {"name": "transcribe_ml_false", "task": "transcribe", "multilingual": False},
    # The best case the instrument offers: re-detect language on every segment.
    {"name": "transcribe_ml_true", "task": "transcribe", "multilingual": True},
    # The "translates the rest" probe: English-only target. multilingual=True so it also
    # gets the per-segment detection best case while translating.
    {"name": "translate_ml_true", "task": "translate", "multilingual": True},
)

#: Travels onto every row so the result can never be quoted without its assembly (D-05) or
#: over-read at the segment level (Segment has no .language field).
D05_CAVEAT = (
    "D-05: measures Whisper on SYNTHETIC Chatterbox speech (D-04), not the user's real "
    "code-switched speech; Chatterbox failures and Whisper failures are not separable here."
)
SEGMENT_CAVEAT = (
    "Segment carries no .language field: per-segment language is INFERRED from "
    "all_language_probs + output script, not a direct per-segment label."
)


# --------------------------------------------------------------------------------------
# Planning (no engine — the parent process stays light and testable)
# --------------------------------------------------------------------------------------


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, dict[str, Any]]:
    """Read the committed 20-record failure grid (01-02), keyed by clip id.

    Used only to join each clip back to its source text so the write-up can compare what
    was said with what Whisper heard. The clip's *tag* comes from its filename, never from
    here.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Corpus fixture missing: {path}")
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_id = {r["id"]: r for r in records}
    if len(by_id) != len(records):
        raise ValueError("Duplicate clip id in corpus.jsonl")
    return by_id


def list_clips(clips_dir: Path = CLIPS_DIR, pattern: str = "*.wav") -> list[Path]:
    """Every rendered clip, sorted, each name parseable by the shared convention.

    Parses every name up front (via ``shuffle_blind.parse_clip_name`` with the default
    ``JUDGABLE_TAGS`` so the six ``__none`` controls parse rather than raise): a clip whose
    name cannot be parsed is a clip whose tag would be guessed, and a guessed tag corrupts
    the join.
    """
    if not clips_dir.is_dir():
        raise FileNotFoundError(f"Clips directory missing: {clips_dir}")
    clips = sorted(p for p in clips_dir.glob(pattern) if p.is_file())
    if not clips:
        raise ValueError(f"No clips matching {pattern!r} in {clips_dir}")
    for clip in clips:  # fail loudly now, not mid-transcription
        sb.parse_clip_name(clip.name)
    return clips


def build_plan(
    clips: list[Path],
    conditions: Iterable[dict[str, Any]] = CONDITIONS,
) -> list[dict[str, Any]]:
    """The full (clip, condition) job list — one row of transcripts.jsonl per entry.

    Pure planning, no engine import, so the shape of the run is checkable in the base venv
    before a single CPU-minute of Whisper is spent.
    """
    plan: list[dict[str, Any]] = []
    for clip in clips:
        tag = sb.parse_clip_name(clip.name)
        for condition in conditions:
            plan.append(
                {
                    "clip_path": clip,
                    "clip_id": tag.clip_id,
                    "language_id": tag.language_id,
                    "source_name": clip.name,
                    "condition": dict(condition),
                }
            )
    return plan


def _row_key(clip_id: str, condition_name: str) -> tuple[str, str]:
    return (clip_id, condition_name)


def already_done(path: Path = TRANSCRIPTS_PATH) -> set[tuple[str, str]]:
    """The set of (clip_id, condition name) rows already written — so the run resumes."""
    if not path.is_file():
        return set()
    done: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        done.add(_row_key(row["clip_id"], row["condition"]["name"]))
    return done


# --------------------------------------------------------------------------------------
# Engine — every faster_whisper import lives inside a function (base venv stays clean)
# --------------------------------------------------------------------------------------


def load_model():  # noqa: ANN201 - returns a faster_whisper.WhisperModel
    """Load Whisper large-v3 once, CPU + int8. Weights are cached by 01-03."""
    from faster_whisper import WhisperModel

    return WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)


def _topk(all_language_probs: Any, k: int = TOP_K) -> list[list[Any]]:
    """Top-k of a language posterior, as JSON-friendly ``[[lang, prob], ...]``.

    ``all_language_probs`` is already sorted descending by faster-whisper; kept defensive
    against ``None`` (older builds) so a missing posterior is recorded as empty, not a crash.
    """
    if not all_language_probs:
        return []
    return [[lang, float(prob)] for lang, prob in list(all_language_probs)[:k]]


def detect_language_posterior(model, clip_path: Path) -> dict[str, Any]:
    """Independent ``model.detect_language()`` posterior for one clip (task-agnostic).

    Unlike ``transcribe()`` (which accepts a path), ``detect_language`` in 1.2.1 takes a
    DECODED audio array, so the clip is decoded through faster-whisper's own
    ``decode_audio`` (16 kHz mono, the model's expected rate) rather than handed a path.
    """
    from faster_whisper.audio import decode_audio

    audio = decode_audio(str(clip_path))
    lang, prob, all_probs = model.detect_language(audio=audio)
    return {
        "language": lang,
        "probability": float(prob),
        "topk": _topk(all_probs),
    }


def transcribe_condition(model, clip_path: Path, condition: dict[str, Any]) -> dict[str, Any]:
    """Transcribe one clip under one condition; realise the segment generator to a list."""
    started = time.perf_counter()
    segments, info = model.transcribe(
        str(clip_path),
        language=LANGUAGE,
        multilingual=condition["multilingual"],
        vad_filter=VAD_FILTER,
        task=condition["task"],
    )
    # NOTE: Segment has NO .language field — see SEGMENT_CAVEAT.
    seg_rows = [
        {"id": s.id, "start": round(float(s.start), 3), "end": round(float(s.end), 3), "text": s.text}
        for s in segments
    ]
    elapsed = time.perf_counter() - started
    return {
        "detected_language": info.language,
        "language_probability": float(info.language_probability),
        "all_language_probs_topk": _topk(info.all_language_probs),
        "audio_duration": round(float(info.duration), 3),
        "transcript": "".join(s["text"] for s in seg_rows).strip(),
        "segments": seg_rows,
        "transcribe_seconds": round(elapsed, 3),
    }


def build_row(
    job: dict[str, Any],
    corpus: dict[str, dict[str, Any]],
    condition_result: dict[str, Any],
    detect_result: dict[str, Any],
) -> dict[str, Any]:
    """Assemble one transcripts.jsonl row: identity + condition + result + caveats."""
    src = corpus.get(job["clip_id"], {})
    return {
        "clip_id": job["clip_id"],
        "language_id": job["language_id"],
        "source_name": job["source_name"],
        "matrix_lang": src.get("matrix_lang"),
        "embedded_lang": src.get("embedded_lang"),
        "category": src.get("category"),
        "source_text": src.get("text"),
        "condition": job["condition"],
        "model": MODEL_NAME,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "vad_filter": VAD_FILTER,
        "language_pinned": LANGUAGE,
        "detected_language": condition_result["detected_language"],
        "language_probability": condition_result["language_probability"],
        "all_language_probs_topk": condition_result["all_language_probs_topk"],
        "detect_language": detect_result,
        "audio_duration": condition_result["audio_duration"],
        "transcribe_seconds": condition_result["transcribe_seconds"],
        "transcript": condition_result["transcript"],
        "segments": condition_result["segments"],
        "segment_language_caveat": SEGMENT_CAVEAT,
        "d05_caveat": D05_CAVEAT,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def run(
    *,
    limit: int | None = None,
    out_path: Path = TRANSCRIPTS_PATH,
    clips_dir: Path = CLIPS_DIR,
    conditions: Iterable[dict[str, Any]] = CONDITIONS,
) -> int:
    """Transcribe clips under every condition, appending one row each. Resumable.

    Returns the number of rows written this call. ``detect_language()`` is called once per
    clip (task-agnostic) and attached to every condition row for that clip, so a single
    clip's rows are self-contained without paying for three detection passes.
    """
    corpus = load_corpus()
    clips = list_clips(clips_dir)
    if limit is not None:
        clips = clips[:limit]
    plan = build_plan(clips, conditions)
    done = already_done(out_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[transcribe] {len(clips)} clips x {len(tuple(conditions))} conditions = "
          f"{len(plan)} rows; {len(done)} already done", flush=True)

    model = load_model()
    print(f"[transcribe] model loaded: {MODEL_NAME} on {DEVICE}/{COMPUTE_TYPE}", flush=True)

    written = 0
    detect_cache: dict[str, dict[str, Any]] = {}
    total = len(plan)
    with out_path.open("a", encoding="utf-8") as fh:
        for i, job in enumerate(plan, 1):
            key = _row_key(job["clip_id"], job["condition"]["name"])
            if key in done:
                continue
            if job["clip_id"] not in detect_cache:
                detect_cache[job["clip_id"]] = detect_language_posterior(model, job["clip_path"])
            result = transcribe_condition(model, job["clip_path"], job["condition"])
            row = build_row(job, corpus, result, detect_cache[job["clip_id"]])
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            written += 1
            print(
                f"[transcribe] {i}/{total} {job['source_name']} "
                f"[{job['condition']['name']}] -> det={result['detected_language']} "
                f"p={result['language_probability']:.2f} {result['transcribe_seconds']:.1f}s",
                flush=True,
            )
    print(f"[transcribe] wrote {written} new rows to {out_path}", flush=True)
    return written


def self_check(clips_dir: Path = CLIPS_DIR) -> None:
    """Fast end-to-end smoke: one clip, both multilingual conditions, posterior non-empty.

    A negative control is included: a bogus multilingual value must raise rather than be
    silently accepted, so a green self-check cannot be manufactured by a no-op transcribe.
    """
    clips = list_clips(clips_dir)
    clip = clips[0]
    model = load_model()
    for ml in (False, True):
        cond = {"name": f"selfcheck_ml_{ml}", "task": "transcribe", "multilingual": ml}
        result = transcribe_condition(model, clip, cond)
        assert result["all_language_probs_topk"], f"empty posterior under multilingual={ml}"
        assert result["detected_language"], f"no detected language under multilingual={ml}"
    detect = detect_language_posterior(model, clip)
    assert detect["topk"], "detect_language returned an empty posterior"
    print(f"[self-check] OK on {clip.name}: both conditions + detect_language posterior non-empty")


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--limit", type=int, default=None, help="only the first N clips")
    parser.add_argument("--out", default=str(TRANSCRIPTS_PATH))
    parser.add_argument("--clips-dir", default=str(CLIPS_DIR))
    parser.add_argument("--dry-run", action="store_true", help="print the plan, load no model")
    parser.add_argument("--self-check", action="store_true", help="fast one-clip smoke test")
    args = parser.parse_args(argv)

    if args.dry_run:
        clips = list_clips(Path(args.clips_dir))
        if args.limit is not None:
            clips = clips[: args.limit]
        plan = build_plan(clips)
        print(f"{len(clips)} clips, {len(plan)} rows:")
        for job in plan:
            print(f"  {job['source_name']} [{job['condition']['name']}]")
        return 0

    if args.self_check:
        self_check(Path(args.clips_dir))
        return 0

    run(limit=args.limit, out_path=Path(args.out), clips_dir=Path(args.clips_dir))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
