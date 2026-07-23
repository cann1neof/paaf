"""Render the SPIKE-01 failure-grid corpus through Chatterbox Multilingual V3.

THROWAWAY (SC#5 / D-18) — this file dies with ``spike/``. What survives is what it
writes: ``.planning/phases/01-spike-gate/corpus/clips/*.wav`` and ``timings.jsonl``,
declared DATA under D-07, which Phase 7 SC#1 mechanically re-runs and diffs against.

What this produces
------------------
Per D-06 each corpus sentence is rendered **twice** — once tagged with its ``matrix_lang``
and once with its ``embedded_lang`` — giving 40 clips from the 20-record corpus. On top of
that, a labeled subset gets a **third** render with ``language_id=None`` (RESEARCH Open
Q5). That control is not decoration: without it, "the tagged renders sound the same" is
ambiguous between *the tag did nothing* and *the tag did the wrong thing*. The subset is
one sentence per D-02 category, derived from the corpus rather than hard-coded, so it
cannot drift if the corpus is edited.

Four properties this harness is built to guarantee
--------------------------------------------------
1. **The Dicta repair is ACTIVE in every render process** (01-03). ``chatterbox-tts``
   0.1.7 calls ``Dicta()`` with no arguments against a constructor that requires
   ``model_path``, and swallows the ``TypeError`` — Hebrew then reaches the model as a
   consonant skeleton and the resulting WAVs look *identical* to good ones. Because
   Pattern 2 renders in fresh subprocesses, chatterbox's module-level ``_dicta`` global is
   re-initialised every batch, so the repair has to be re-applied and re-asserted every
   batch. This module asserts it (``_assert_repair_active``) rather than assuming it, and
   the assertion runs before any clip in the batch is written.
2. **Per-call seeding** (Pitfall 6). ``torch.manual_seed(SEED)`` immediately before *each*
   ``generate()``, never once per process — batching and subprocess boundaries would
   otherwise shift the RNG stream. 01-03 measured seeded synthesis bitwise identical on
   MPS, so D-07's re-run-and-diff promise is a promise this render can actually keep.
3. **Leak-isolated batches** (Pattern 2 / Pitfall 5). Clips are rendered ``BATCH_SIZE`` at
   a time in a fresh subprocess. The reported 222–800 MB-per-few-generations accumulation
   on Apple Silicon would otherwise reach swap on an 18 GB machine well within 46 clips,
   and every timing taken after the pressure starts would be silently wrong.
4. **Failure is data, not a blocker** (D-11/D-12). If MPS dies mid-render the exception is
   recorded verbatim into ``timings.jsonl`` and the render continues on CPU. An unusable
   MPS is a *measurement*, and one that bears on the deferred hardware purchase.

What these timings are NOT
--------------------------
``timings.jsonl`` is SPIKE-01 **secondary** data. It is not the SPIKE-03 latency metric:
per Pitfall 5 that number must be taken in a dedicated single-purpose process, which is
01-09's job. Read these numbers as "how long the corpus took", not as TTFA.

Watermarking (Pitfall 11 / VOICE-12)
------------------------------------
``generate()`` unconditionally calls ``apply_watermark`` and there is no flag to disable
it. It sits **inside** the timed region here, so every ``synth_seconds`` below includes
PerTh watermarking. Recorded, not worked around — it is a property of the default engine.

Usage
-----
    # render everything still missing, in leak-isolated batches
    spike/voice/.venv/bin/python spike/voice/render_corpus.py

    # bounded run (resumable — already-rendered clips are skipped)
    spike/voice/.venv/bin/python spike/voice/render_corpus.py --max-batches 2

    # what would be rendered, without loading a model
    spike/voice/.venv/bin/python spike/voice/render_corpus.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
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
BLIND_DIR = CORPUS_DIR / "clips_blind"
MAPPING_PATH = CORPUS_DIR / "mapping.json"
TIMINGS_PATH = CORPUS_DIR / "timings.jsonl"

#: Pitfall 6. Same value GATE 0 proved reproducible on this backend (01-03), so the two
#: bodies of evidence are comparable rather than merely each self-consistent.
FIXED_SEED = 1234

#: Pattern 2: N≈5–8 clips per fresh process. 6 keeps peak accumulation ~<5 GB at the
#: reported worst case while still amortising the ~40 s cold model load over six clips.
BATCH_SIZE = 6

#: Device preference. The STRING is mandatory (Pitfall 4): chatterbox's from_pretrained
#: does `device == "mps"`, a string comparison, despite its torch.device type hint.
#: 01-03 measured `mps` usable on this machine.
DEVICE_ORDER = ("mps", "cpu")

#: Every generation parameter, stated explicitly rather than inherited from a default, so
#: the record in timings.jsonl is the record of what actually ran.
GEN_PARAMS: dict[str, float] = {
    "exaggeration": 0.5,
    "cfg_weight": 0.5,
    "temperature": 0.8,
    "repetition_penalty": 2.0,
    "min_p": 0.05,
    "top_p": 1.0,
}

#: The three conditions. "none" is the untagged control (RESEARCH Open Q5).
CONDITION_MATRIX = "matrix"
CONDITION_EMBEDDED = "embedded"
CONDITION_NONE = "none"

#: Hebrew consonant probe used to prove the Dicta repair is live in THIS process.
HEBREW_REPAIR_PROBE = "שלום עולם"


# --------------------------------------------------------------------------------------
# Job planning (no torch — the parent process must stay light)
# --------------------------------------------------------------------------------------


def load_corpus(path: Path = CORPUS_PATH) -> list[dict[str, Any]]:
    """Read the committed 20-record failure grid (01-02)."""
    if not path.is_file():
        raise FileNotFoundError(f"Corpus fixture missing: {path}")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError(f"{path} is empty")
    return records


def none_control_ids(records: Iterable[dict[str, Any]]) -> list[str]:
    """One sentence per D-02 category, for the ``language_id=None`` control.

    Derived from the corpus (first record of each category, in file order) rather than
    hard-coded: a hard-coded list silently stops covering all six categories the moment
    the corpus is edited, and the control's value is precisely that it spans the same
    failure grid the tagged renders do.
    """
    chosen: dict[str, str] = {}
    for rec in records:
        chosen.setdefault(rec["category"], rec["id"])
    return sorted(chosen.values())


def build_jobs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The full render plan: matrix + embedded per record (D-06), plus the control subset."""
    controls = set(none_control_ids(records))
    jobs: list[dict[str, Any]] = []
    for rec in records:
        conditions: list[tuple[str, str | None]] = [
            (CONDITION_MATRIX, rec["matrix_lang"]),
            (CONDITION_EMBEDDED, rec["embedded_lang"]),
        ]
        if rec["id"] in controls:
            conditions.append((CONDITION_NONE, None))
        for condition, language_id in conditions:
            jobs.append(
                {
                    "clip_id": rec["id"],
                    "text": rec["text"],
                    "category": rec["category"],
                    "matrix_lang": rec["matrix_lang"],
                    "embedded_lang": rec["embedded_lang"],
                    "condition": condition,
                    "language_id": language_id,
                    # One definition of the convention, called — never re-implemented (01-02).
                    "filename": sb.clip_filename(rec["id"], language_id),
                }
            )
    return jobs


def pending(jobs: list[dict[str, Any]], clips_dir: Path, force: bool) -> list[dict[str, Any]]:
    """Jobs whose WAV is not already on disk. Makes a long render resumable."""
    if force:
        return list(jobs)
    return [j for j in jobs if not (clips_dir / j["filename"]).is_file()]


def batched(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def append_rows(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------------------
# Worker — runs inside a fresh subprocess, one batch, then dies (Pattern 2)
# --------------------------------------------------------------------------------------


def _assert_repair_active(model_path: str | None) -> dict[str, Any]:
    """Apply the 01-03 Dicta repair and PROVE it took effect in this process.

    Assumption is not available here. A subprocess that skipped the repair emits Hebrew
    from a consonant skeleton, and those WAVs are indistinguishable from good ones by
    inspection — they would silently destroy the SPIKE-02 measurement while looking like
    a completed render. So: mutate a known Hebrew string and refuse to render if it comes
    back unchanged.
    """
    import gate_readiness as gr
    import chatterbox.models.tokenizers.tokenizer as tok

    gr.reset_dicta()
    native = gr.probe_native_dicta_construction()
    gr.repair_dicta(model_path)

    with gr.capture_logs() as records:
        out = tok.add_hebrew_diacritics(HEBREW_REPAIR_PROBE)

    if out == HEBREW_REPAIR_PROBE:
        raise gr.GateFailure(
            "Dicta repair did NOT take effect in this render subprocess: "
            f"{HEBREW_REPAIR_PROBE!r} came back unchanged. Refusing to render — Hebrew "
            "would be synthesized from a consonant skeleton and the clips would look fine."
        )
    bad = gr.degradation_records(records)
    if bad:
        raise gr.GateFailure(
            f"degradation path active in this render subprocess: {[r.getMessage() for r in bad]}"
        )
    return {
        "configuration": gr.CONFIG_REPAIRED,
        "native_zero_arg_dicta_works": native.ok,
        "probe_in": HEBREW_REPAIR_PROBE,
        "probe_out": out,
        "dicta_model_path": str(gr.resolve_dicta_model_path(model_path)),
    }


def run_worker(jobs_path: Path, out_path: Path, device: str, seed: int, model_path: str | None) -> int:
    """Render one batch. Every row is flushed as it is produced, so a crash keeps data."""
    import soundfile as sf
    import torch

    import chatterbox
    import gate_readiness as gr
    from chatterbox import ChatterboxMultilingualTTS

    payload = json.loads(jobs_path.read_text(encoding="utf-8"))
    jobs: list[dict[str, Any]] = payload["jobs"]
    batch_index: int = payload["batch_index"]

    repair = _assert_repair_active(model_path)

    load_t0 = time.perf_counter()
    tts = ChatterboxMultilingualTTS.from_pretrained(device=device)  # STRING (Pitfall 4)
    load_seconds = time.perf_counter() - load_t0

    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": torch.__version__,
        "chatterbox": chatterbox.__version__,
        "pid": os.getpid(),
    }

    with out_path.open("w", encoding="utf-8") as fh:
        for index, job in enumerate(jobs):
            with gr.capture_logs() as records:
                # Pitfall 6: per CALL, not per process. Subprocess boundaries and batch
                # position must not be able to shift the RNG stream.
                torch.manual_seed(seed)
                t0 = time.perf_counter()
                wav = tts.generate(  # watermarking is unconditional and INSIDE this region
                    job["text"],
                    language_id=job["language_id"],
                    **GEN_PARAMS,
                )
                synth_seconds = time.perf_counter() - t0

            degraded = [f"{r.name}: {r.getMessage()}" for r in gr.degradation_records(records)]
            others = sorted({f"{r.name}: {r.getMessage()}" for r in gr.other_warnings(records)})

            samples = wav.squeeze(0).detach().float().cpu().numpy()
            out_wav = CLIPS_DIR / job["filename"]
            out_wav.parent.mkdir(parents=True, exist_ok=True)
            sf.write(out_wav, samples, tts.sr)

            row = {
                "clip_id": job["clip_id"],
                "tag": sb.parse_clip_name(job["filename"]).language_id,
                "condition": job["condition"],
                "language_id": job["language_id"],
                "category": job["category"],
                "filename": job["filename"],
                "device": device,
                "seed": seed,
                "gen_params": GEN_PARAMS,
                "synth_seconds": round(synth_seconds, 4),
                "model_load_seconds": round(load_seconds, 4),
                "position_in_batch": index,
                "batch_index": batch_index,
                "sample_rate": int(tts.sr),
                "samples": int(samples.shape[-1]),
                "duration_seconds": round(float(samples.shape[-1]) / float(tts.sr), 4),
                "bytes": out_wav.stat().st_size,
                "watermarked": True,  # Pitfall 11 / VOICE-12: no flag exists to disable it
                "watermark_inside_timed_region": True,
                "degradation_warnings": degraded,
                "other_warnings": others,
                "configuration": repair["configuration"],
                "native_zero_arg_dicta_works": repair["native_zero_arg_dicta_works"],
                "dicta_probe_out": repair["probe_out"],
                "environment": env,
                "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "ok": True,
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(
                f"    [{device}] {job['filename']:<16} "
                f"{row['duration_seconds']:>6.2f}s audio in {synth_seconds:>6.1f}s"
                + (f"  ⚠ {degraded}" if degraded else ""),
                flush=True,
            )

            if degraded:
                raise gr.GateFailure(
                    f"chatterbox degradation warning fired while rendering {job['filename']}: "
                    f"{degraded}. Refusing to continue — the remaining clips would be suspect."
                )
    return 0


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------


def _failure_row(batch: list[dict[str, Any]], device: str, seed: int, exc_text: str, batch_index: int) -> dict[str, Any]:
    """A device failure is a recorded MEASUREMENT (D-11/D-12), never a swallowed error."""
    return {
        "clip_id": None,
        "tag": None,
        "condition": "batch-failure",
        "language_id": None,
        "filename": None,
        "device": device,
        "seed": seed,
        "batch_index": batch_index,
        "batch_filenames": [j["filename"] for j in batch],
        "ok": False,
        "exception_verbatim": exc_text,
        "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": (
            "Batch subprocess exited non-zero. Per D-11/D-12 the failure of a device is a "
            "valid recorded outcome, not a phase blocker; the driver falls to the next "
            "device in DEVICE_ORDER and continues."
        ),
    }


def run_batch(batch: list[dict[str, Any]], batch_index: int, device: str, seed: int, model_path: str | None) -> tuple[bool, list[dict[str, Any]], str]:
    """Spawn a fresh process for one batch. Returns ``(ok, rows, stderr_tail)``."""
    with tempfile.TemporaryDirectory() as tmp:
        jobs_file = Path(tmp) / "jobs.json"
        rows_file = Path(tmp) / "rows.jsonl"
        jobs_file.write_text(
            json.dumps({"batch_index": batch_index, "jobs": batch}, ensure_ascii=False),
            encoding="utf-8",
        )
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--jobs-file", str(jobs_file),
            "--rows-file", str(rows_file),
            "--device", device,
            "--seed", str(seed),
        ]
        if model_path:
            cmd += ["--dicta-model", model_path]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        sys.stdout.write(proc.stdout)
        sys.stdout.flush()

        rows: list[dict[str, Any]] = []
        if rows_file.is_file():
            rows = [
                json.loads(line)
                for line in rows_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        return proc.returncode == 0, rows, (proc.stderr or "")[-4000:]


def drive(args: argparse.Namespace) -> int:
    records = load_corpus()
    jobs = build_jobs(records)
    todo = pending(jobs, CLIPS_DIR, args.force)

    controls = none_control_ids(records)
    print(
        f"corpus={len(records)} records -> {len(jobs)} clips "
        f"({2 * len(records)} matrix+embedded per D-06, {len(controls)} untagged controls "
        f"on {controls})"
    )
    print(f"already rendered: {len(jobs) - len(todo)}   pending: {len(todo)}")
    if args.dry_run:
        for j in todo:
            print(f"  {j['filename']:<16} condition={j['condition']:<8} language_id={j['language_id']}")
        return 0
    if not todo:
        print("nothing to render.")
        return 0

    batches = batched(todo, args.batch_size)
    if args.max_batches is not None:
        batches = batches[: args.max_batches]

    device_index = DEVICE_ORDER.index(args.device) if args.device in DEVICE_ORDER else 0
    started = time.perf_counter()
    rendered = 0

    for offset, batch in enumerate(batches):
        batch_index = offset
        print(
            f"\n=== batch {offset + 1}/{len(batches)} — {len(batch)} clips — "
            f"fresh subprocess (Pattern 2) — elapsed {time.perf_counter() - started:.0f}s ===",
            flush=True,
        )
        while True:
            device = DEVICE_ORDER[device_index]
            ok, rows, stderr_tail = run_batch(batch, batch_index, device, args.seed, args.dicta_model)
            append_rows(TIMINGS_PATH, rows)
            rendered += len(rows)
            if ok:
                break
            append_rows(TIMINGS_PATH, [_failure_row(batch, device, args.seed, stderr_tail, batch_index)])
            print(f"!! batch failed on device={device}; recorded verbatim as data", file=sys.stderr)
            print(stderr_tail, file=sys.stderr)
            if device_index + 1 >= len(DEVICE_ORDER):
                print("!! no device left to fall back to — stopping", file=sys.stderr)
                return 1
            device_index += 1
            # Re-plan the batch: whatever this attempt did manage to write is already on
            # disk and must not be re-rendered under a different device.
            batch = pending(batch, CLIPS_DIR, force=False)
            if not batch:
                break
            print(f"   falling back to device={DEVICE_ORDER[device_index]} for the remaining "
                  f"{len(batch)} clips (D-11/D-12: an unusable device is a result)", file=sys.stderr)

    still = pending(jobs, CLIPS_DIR, force=False)
    print(
        f"\nrendered {rendered} clip(s) this invocation in "
        f"{time.perf_counter() - started:.0f}s; {len(still)} still pending"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--jobs-file", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--rows-file", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--device", default=DEVICE_ORDER[0], help="starting device (STRING, Pitfall 4)")
    ap.add_argument("--seed", type=int, default=FIXED_SEED)
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--max-batches", type=int, default=None, help="stop after N batches (resumable)")
    ap.add_argument("--force", action="store_true", help="re-render clips that already exist")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dicta-model", default=None, help="path to dicta-1.0.onnx")
    args = ap.parse_args(argv)

    if args.worker:
        return run_worker(
            Path(args.jobs_file), Path(args.rows_file), args.device, args.seed, args.dicta_model
        )
    return drive(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
