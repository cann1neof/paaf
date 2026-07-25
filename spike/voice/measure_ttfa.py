"""SPIKE-03 — Chatterbox time-to-first-audio (TTFA) for ONE short sentence, on
Mac ``mps`` AND Mac ``cpu`` (D-11), warm (cold model-load + first synth excluded).

THROWAWAY (SC#5 / D-18) — this file dies with ``spike/``. What survives is what it
writes: ``.planning/phases/01-spike-gate/raw/ttfa.md`` (Task 2 reads the JSON this prints).

Why this is a DEDICATED single-purpose process (Pitfall 5)
---------------------------------------------------------
01-05's ``timings.jsonl`` is NOT a latency metric — it is contaminated by batch position
and per-batch model reload. TTFA must be taken in a process that does exactly one thing:
load the model once, then time repeated synthesis of one short sentence. Anything else
(the corpus render's batching, subprocess churn, disk writes per clip) leaks into the
number and directs a hardware purchase on fiction.

What TTFA IS here (Pitfall 3)
-----------------------------
Chatterbox exposes NO streaming/first-chunk API — ``generate()`` returns the whole
waveform. So "time to first audio" for a single short utterance == the wall-clock of one
``generate()`` call returning (there is no earlier "first audio" moment to measure). That
is the honest definition for this engine, and it matches SESS-02's "one short sentence".

Warm vs cold (D-11 / Pitfall 10)
--------------------------------
A user pays the cold start once per process launch. We report BOTH, separated:

* ``cold_total_seconds`` = model-load + the first ``generate()`` (MPS kernel compilation,
  lazy init). This is the true cold-start a user feels on the first utterance.
* ``warm_seconds``       = every subsequent ``generate()`` of the same sentence, the
  steady-state latency that dominates a running assistant. The first (cold) generate is
  DISCARDED from the warm statistics.

Watermarking (Pitfall 11 / VOICE-12)
------------------------------------
Chatterbox watermarks unconditionally and there is no flag to disable it. That cost is
INSIDE the timed region here, exactly as it is for a real user — the number would be a
lie otherwise. Recorded as such.

Device string (Pitfall 4)
-------------------------
``device`` is the STRING ``"mps"`` / ``"cpu"``; chatterbox's ``from_pretrained`` does a
string ``== "mps"`` comparison despite the ``torch.device`` type hint. An ``mps`` failure
is a RESULT (D-11/D-12), captured verbatim, not a crash.

Engine imports live INSIDE functions so the accounting logic (``warm_beats_cold``,
``summarize``) is importable and testable in the base venv with no torch.

Usage
-----
    # both devices, 5 warm iterations each (the default)
    spike/voice/.venv/bin/python spike/voice/measure_ttfa.py

    # one device (mps is fast, cpu is slow — split them across calls when timing out)
    spike/voice/.venv/bin/python spike/voice/measure_ttfa.py --device cpu --n-warm 3

    # write the machine-readable result for Task 2
    spike/voice/.venv/bin/python spike/voice/measure_ttfa.py --json-out spike/voice/.ttfa.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT = Path(__file__).resolve().parents[2]

#: One short, representative assistant utterance. English keeps the CPU baseline bounded
#: and is the common short-reply case; the Hebrew diacritics path is therefore not on the
#: timed region for this sentence (noted in ttfa.md). Recorded verbatim so the number is
#: attributable to an exact input.
SENTENCE = "Set a timer for ten minutes."

#: Devices to probe, STRINGS (Pitfall 4). 01-03 measured mps usable; the cpu baseline was
#: never taken, so D-12's hardware-class inference is one-sided until this plan runs it.
DEVICES = ("mps", "cpu")

#: Fixed per-call seed (Pitfall 6): set immediately before EACH generate() so run-to-run
#: variance is latency, not RNG drift.
SEED = 1234

#: Every generation parameter stated explicitly (D-07) — the same set 01-05 rendered with,
#: so the TTFA number describes the same pipeline the corpus was produced by.
GEN_PARAMS: dict[str, float] = {
    "exaggeration": 0.5,
    "cfg_weight": 0.5,
    "temperature": 0.8,
    "repetition_penalty": 2.0,
    "min_p": 0.05,
    "top_p": 1.0,
}

DEFAULT_JSON_OUT = Path(__file__).resolve().parent / ".ttfa.json"


# --------------------------------------------------------------------------------------
# Accounting — pure, engine-free, testable in the base venv
# --------------------------------------------------------------------------------------


def summarize(cold_total_seconds: float, warm_seconds: list[float]) -> dict[str, Any]:
    """Reduce raw warm timings to p50/p95/min/max alongside the cold-start total.

    ``warm_seconds`` must already have the first (cold) generate removed.
    """
    if not warm_seconds:
        raise ValueError("no warm samples — the cold run must not be the only measurement")
    ordered = sorted(warm_seconds)
    return {
        "cold_total_seconds": round(cold_total_seconds, 4),
        "warm_n": len(ordered),
        "warm_p50_seconds": round(statistics.median(ordered), 4),
        # nearest-rank p95 without numpy; on small n this is max, which is the honest
        # worst case a buyer needs to see (variance is not averaged away).
        "warm_p95_seconds": round(ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))], 4),
        "warm_min_seconds": round(ordered[0], 4),
        "warm_max_seconds": round(ordered[-1], 4),
        "warm_samples_seconds": [round(v, 4) for v in warm_seconds],
    }


def warm_beats_cold(result: dict[str, Any]) -> bool:
    """True iff warm steady-state latency is strictly below the cold-start total.

    This is the SPIKE-03 integrity check (VALIDATION: SPIKE-03 warm<cold). It CAN fail —
    the negative control in the test feeds a result where warm == cold and asserts False —
    so a green here means the warmup discipline actually changed the number, not that the
    check is vacuous.
    """
    if not result.get("ok"):
        return False
    return result["warm_p50_seconds"] < result["cold_total_seconds"]


# --------------------------------------------------------------------------------------
# Measurement — engine imports inside (base venv stays torch-free)
# --------------------------------------------------------------------------------------


def measure_one_device(device: str, n_warm: int = 5, seed: int = SEED,
                       sentence: str = SENTENCE) -> dict[str, Any]:
    """Load Chatterbox on ``device``, time the cold start, then ``n_warm`` warm generates.

    An ``mps`` failure is recorded VERBATIM (exception type, repr, str, traceback) and
    returned as ``ok=False`` — a valid, reportable result per D-11/D-12, never a raised
    crash that would abort the whole measurement.
    """
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        import torch
        import chatterbox
        import gate_readiness as gr
        from chatterbox import ChatterboxMultilingualTTS

        # Faithful pipeline: apply and prove the 01-03 Dicta repair, so this measures the
        # SAME assembly 01-05 rendered with. Cost is OUTSIDE the timed region below.
        gr.reset_dicta()
        gr.repair_dicta()

        load_t0 = time.perf_counter()
        tts = ChatterboxMultilingualTTS.from_pretrained(device=device)  # STRING (Pitfall 4)
        model_load_seconds = time.perf_counter() - load_t0

        def one_generate() -> float:
            torch.manual_seed(seed)  # Pitfall 6: immediately before EACH call
            t0 = time.perf_counter()
            _ = tts.generate(  # watermarking is unconditional and INSIDE this timed region
                sentence,
                language_id="en",
                **GEN_PARAMS,
            )
            return time.perf_counter() - t0

        # Cold run #1 — DISCARDED from warm stats (Pitfall 10). The user-felt cold start is
        # model load + this first generate together.
        cold_generate_seconds = one_generate()
        cold_total_seconds = model_load_seconds + cold_generate_seconds

        warm_seconds = [one_generate() for _ in range(n_warm)]

        stats = summarize(cold_total_seconds, warm_seconds)
        return {
            "device": device,
            "ok": True,
            "sentence": sentence,
            "seed": seed,
            "gen_params": GEN_PARAMS,
            "model_load_seconds": round(model_load_seconds, 4),
            "cold_generate_seconds": round(cold_generate_seconds, 4),
            "ttfa_definition": (
                "no streaming API (Pitfall 3): TTFA == wall-clock of one generate() "
                "returning the full waveform for one short sentence"
            ),
            "watermark_inside_timed_region": True,
            "torch": torch.__version__,
            "chatterbox": chatterbox.__version__,
            "started_at": started_at,
            **stats,
        }
    except Exception as exc:  # noqa: BLE001 — the failure IS the measurement (D-11/D-12)
        return {
            "device": device,
            "ok": False,
            "sentence": sentence,
            "error_type": type(exc).__name__,
            "error_repr": repr(exc),
            "error_str": str(exc),
            "traceback": traceback.format_exc(),
            "note": (
                "This device is UNUSABLE for Chatterbox on this machine. Per D-11/D-12 "
                "that is a recorded result, not a phase failure — the verbatim exception "
                "is the evidence."
            ),
            "started_at": started_at,
        }


def run(devices: tuple[str, ...] = DEVICES, n_warm: int = 5,
        json_out: Path | None = None) -> list[dict[str, Any]]:
    """Measure every requested device, print a JSON summary, optionally persist it."""
    results = []
    for device in devices:
        print(f"[ttfa] measuring device={device!r} (1 cold + {n_warm} warm) …", flush=True)
        r = measure_one_device(device, n_warm=n_warm)
        if r["ok"]:
            print(
                f"[ttfa] {device}: cold_total={r['cold_total_seconds']:.2f}s "
                f"warm_p50={r['warm_p50_seconds']:.2f}s warm_p95={r['warm_p95_seconds']:.2f}s "
                f"warm<cold={warm_beats_cold(r)}",
                flush=True,
            )
        else:
            print(f"[ttfa] {device}: UNUSABLE — {r['error_type']}: {r['error_str']}", flush=True)
        results.append(r)

    payload = {"sentence": SENTENCE, "results": results,
               "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text, flush=True)
    if json_out is not None:
        json_out.write_text(text, encoding="utf-8")
        print(f"[ttfa] wrote {json_out}", flush=True)
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--device", choices=DEVICES, default=None,
                    help="only this device (default: both mps and cpu)")
    ap.add_argument("--n-warm", type=int, default=5, help="warm generates after the cold one")
    ap.add_argument("--json-out", default=str(DEFAULT_JSON_OUT),
                    help="where to persist the JSON result (Task 2 reads it)")
    args = ap.parse_args(argv)

    devices = (args.device,) if args.device else DEVICES
    run(devices=devices, n_warm=args.n_warm, json_out=Path(args.json_out))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
