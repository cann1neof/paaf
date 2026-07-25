"""SPIKE-08 — the Walking Skeleton: a real WAV-in -> STT -> LLM -> TTS -> WAV-out round
trip, with a per-stage latency budget and an explicit ``unattributed`` residual (Pitfall 10).

THROWAWAY (SC#5 / D-18) — dies with ``spike/``. What survives is what it writes:
``.planning/phases/01-spike-gate/raw/roundtrip.md`` (Task 2 reads the JSON this prints).

What this proves
----------------
It is the thinnest end-to-end proof that the voice stack is WIRED and CO-RESIDENT on this
machine: one corpus clip goes in as audio, Whisper transcribes it, the local Ollama latency
model answers it, Chatterbox speaks the answer, and a WAV comes out. If any stage is not
actually connected, this does not run.

The 18 GB constraint (Pitfall 10 — the binding one)
---------------------------------------------------
Chatterbox (~3.2 GB) + Whisper large-v3 (~3 GB) + the Ollama daemon holding qwen3.5:2b
(~2.7 GB) + the Dicta onnx (~1.2 GB) are CO-RESIDENT. That is the whole point (a running
assistant holds all three at once) and also the whole risk: if it swaps, every stage number
is fiction. This harness records this process's peak RSS so a swap-sized footprint is
visible in the record, and it is why the plan MUST run solo.

The small LLM, on purpose (Pitfall 10)
--------------------------------------
The LLM stage uses ``qwen3.5:2b`` — 01-04's LATENCY model, NOT the ``qwen3.5:9b`` bake-off
capability model. SPIKE-08 measures the latency SHAPE a co-resident assistant would feel;
the big model would both distort that shape and blow the memory budget. ``think=False`` and
a bounded ``num_predict`` keep the reply short so the stage measures inference latency, not
essay length.

Per-stage accounting (Pitfall 10 / RESEARCH Open Q4)
----------------------------------------------------
Each stage is timed with its own boundary (``t_stt``, ``t_llm``, ``t_tts``). The wall clock
of the whole trip is timed independently, and ``t_unattributed = wall - (t_stt+t_llm+t_tts)``
is carried EXPLICITLY. A large residual means the harness mis-attributed time — the
accounting is only trustworthy when ``t_unattributed`` is ~0. Iteration 0 is the cold run
and is DISCARDED from the warm p50/p95.

Engine imports live INSIDE functions so the accounting logic (``build_budget``,
``stages_reconstruct_wall``, ``residual_is_small``) is importable/testable in the base venv.

Usage
-----
    spike/voice/.venv/bin/python spike/voice/roundtrip.py                 # 1 cold + 3 warm
    spike/voice/.venv/bin/python spike/voice/roundtrip.py --n-warm 5 --json-out spike/voice/.roundtrip.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / ".planning" / "phases" / "01-spike-gate" / "corpus"
CLIPS_DIR = CORPUS_DIR / "clips"

#: A real user-style request already in the corpus (01-05): "Can you add кефир to the
#: shopping list before we leave?" — English matrix so the LLM gets a coherent prompt.
DEFAULT_INPUT_CLIP = CLIPS_DIR / "c01__en.wav"

#: STT — first-party Systran large-v3, CPU/int8 (CTranslate2 has no Metal backend), the
#: same instrument 01-07 measured with.
STT_MODEL = "large-v3"
STT_DEVICE = "cpu"
STT_COMPUTE_TYPE = "int8"

#: LLM — 01-04's LATENCY model on the local loopback daemon. NOT the 9b capability model.
LLM_MODEL = "qwen3.5:2b"
LLM_HOST = "http://127.0.0.1:11434"
#: Bound the reply so the stage measures latency, not generation length.
LLM_NUM_PREDICT = 64

#: TTS — Chatterbox on mps (01-03 measured usable). Same gen params as the corpus render.
TTS_DEVICE = "mps"
SEED = 1234
GEN_PARAMS: dict[str, float] = {
    "exaggeration": 0.5,
    "cfg_weight": 0.5,
    "temperature": 0.8,
    "repetition_penalty": 2.0,
    "min_p": 0.05,
    "top_p": 1.0,
}

DEFAULT_JSON_OUT = Path(__file__).resolve().parent / ".roundtrip.json"


# --------------------------------------------------------------------------------------
# Accounting — pure, engine-free, testable in the base venv
# --------------------------------------------------------------------------------------

STAGE_KEYS = ("t_stt", "t_llm", "t_tts")


def make_iteration(t_stt: float, t_llm: float, t_tts: float, wall: float) -> dict[str, float]:
    """One timed iteration with the residual forced to close the books against the wall.

    ``t_unattributed`` is DERIVED from the wall clock (never guessed), so the four parts
    always reconstruct the wall — and any real mis-attribution shows up as a non-zero
    residual rather than being silently absorbed into a stage.
    """
    t_unattributed = wall - (t_stt + t_llm + t_tts)
    return {
        "t_stt": t_stt,
        "t_llm": t_llm,
        "t_tts": t_tts,
        "wall": wall,
        "t_unattributed": t_unattributed,
    }


def stages_reconstruct_wall(row: dict[str, float], tol: float = 1e-6) -> bool:
    """Bookkeeping identity: the three stages + residual must sum to the wall.

    This CAN fail — the negative control feeds a row whose residual was computed wrong and
    asserts False — so it is not a vacuous tautology test of the reduction code.
    """
    total = row["t_stt"] + row["t_llm"] + row["t_tts"] + row["t_unattributed"]
    return abs(total - row["wall"]) <= tol


def residual_is_small(row: dict[str, float], rel_tol: float = 0.02, abs_tol: float = 0.05) -> bool:
    """True iff ``t_unattributed`` is ~0 relative to the wall — the accounting is honest.

    A large residual means real time went somewhere the stage boundaries did not capture,
    and the per-stage budget cannot be trusted. Negative control: a row with a big residual
    must return False.
    """
    return abs(row["t_unattributed"]) <= max(abs_tol, rel_tol * row["wall"])


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def build_budget(cold: dict[str, float], warm: list[dict[str, float]]) -> dict[str, Any]:
    """Per-stage table: cold ms | warm p50 ms | warm p95 ms | share of warm-p50 total.

    ``share`` is each stage's fraction of the summed warm-p50 stage times (including the
    unattributed residual), so the shares sum to 1.0 and the dominant stage is unambiguous.
    """
    if not warm:
        raise ValueError("no warm iterations — the cold run must not be the only sample")
    keys = STAGE_KEYS + ("t_unattributed",)
    p50 = {k: statistics.median([w[k] for w in warm]) for k in keys}
    p95 = {k: _pct([w[k] for w in warm], 0.95) for k in keys}
    total_p50 = sum(p50[k] for k in keys)
    wall_p50 = statistics.median([w["wall"] for w in warm])
    label = {"t_stt": "stt", "t_llm": "llm", "t_tts": "tts", "t_unattributed": "unattributed"}
    stages = {}
    for k in keys:
        stages[label[k]] = {
            "cold_ms": round(cold[k] * 1000, 1),
            "warm_p50_ms": round(p50[k] * 1000, 1),
            "warm_p95_ms": round(p95[k] * 1000, 1),
            "share": round(p50[k] / total_p50, 4) if total_p50 else 0.0,
        }
    stages["total"] = {
        "cold_ms": round(cold["wall"] * 1000, 1),
        "warm_p50_ms": round(wall_p50 * 1000, 1),
        "warm_p95_ms": round(_pct([w["wall"] for w in warm], 0.95) * 1000, 1),
        "share": 1.0,
    }
    dominant = max(("stt", "llm", "tts"), key=lambda s: stages[s]["warm_p50_ms"])
    return {"stages": stages, "dominant_stage": dominant,
            "warm_p50_stage_sum_ms": round(total_p50 * 1000, 1)}


# --------------------------------------------------------------------------------------
# Engines — every heavy import inside a function (base venv stays torch-free)
# --------------------------------------------------------------------------------------


def _max_rss_bytes() -> int:
    """Peak resident set of THIS process (holds Whisper + Chatterbox + Dicta).

    stdlib ``resource``; on macOS ``ru_maxrss`` is already in BYTES. Does NOT include the
    separate Ollama daemon — noted in the record. A footprint near the 18 GB ceiling is the
    swap warning sign the buyer needs.
    """
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def load_stt():  # noqa: ANN201
    from faster_whisper import WhisperModel
    return WhisperModel(STT_MODEL, device=STT_DEVICE, compute_type=STT_COMPUTE_TYPE)


def load_llm():  # noqa: ANN201
    """No client object needed — the LLM stage talks to the Ollama daemon over its stable
    REST API via stdlib ``urllib`` (the ``ollama`` package lives in 01-04's bake-off venv,
    not this voice venv, and the framework will speak HTTP to Ollama anyway). Returns the
    base host string so the stage function is self-contained."""
    return LLM_HOST


def load_tts():  # noqa: ANN201
    import gate_readiness as gr
    from chatterbox import ChatterboxMultilingualTTS

    gr.reset_dicta()
    gr.repair_dicta()  # faithful pipeline: a Hebrew reply must synthesize with diacritics
    return ChatterboxMultilingualTTS.from_pretrained(device=TTS_DEVICE)


def stt_transcribe(model, clip_path: Path) -> str:
    segments, _info = model.transcribe(str(clip_path), language=None, vad_filter=False)
    return "".join(s.text for s in segments).strip()


def _strip_think(text: str) -> str:
    """qwen3.5 is a thinking model; drop any leaked <think>…</think> before TTS/logging."""
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def llm_reply(host: str, user_text: str) -> str:
    import urllib.request

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system",
             "content": "You are a terse voice assistant. Reply in one short sentence."},
            {"role": "user", "content": user_text or "Hello."},
        ],
        "stream": False,
        "think": False,  # qwen3.5 is a thinking model; disable so the stage measures reply latency
        "options": {"num_predict": LLM_NUM_PREDICT, "temperature": 0.0},
    }
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return _strip_think(body["message"]["content"]) or "Okay."


def tts_speak(tts, text: str, out_path: Path):  # noqa: ANN201
    import soundfile as sf
    import torch

    torch.manual_seed(SEED)  # Pitfall 6
    wav = tts.generate(text, language_id="en", **GEN_PARAMS)  # watermark inside timed region
    samples = wav.squeeze(0).detach().float().cpu().numpy()
    sf.write(out_path, samples, tts.sr)
    return samples.shape[-1], int(tts.sr)


def one_trip(stt, llm, tts, clip_path: Path, out_path: Path) -> tuple[dict[str, float], dict[str, Any]]:
    """One WAV-in -> WAV-out trip. Returns (timed iteration, artefacts for the record)."""
    wall_t0 = time.perf_counter()

    s0 = time.perf_counter()
    transcript = stt_transcribe(stt, clip_path)
    t_stt = time.perf_counter() - s0

    l0 = time.perf_counter()
    reply = llm_reply(llm, transcript)
    t_llm = time.perf_counter() - l0

    p0 = time.perf_counter()
    n_samples, sr = tts_speak(tts, reply, out_path)
    t_tts = time.perf_counter() - p0

    wall = time.perf_counter() - wall_t0
    row = make_iteration(t_stt, t_llm, t_tts, wall)
    artefacts = {
        "transcript": transcript,
        "reply": reply,
        "out_samples": int(n_samples),
        "out_sample_rate": sr,
        "out_seconds": round(n_samples / sr, 3),
    }
    return row, artefacts


def run(*, n_warm: int = 3, input_clip: Path = DEFAULT_INPUT_CLIP,
        json_out: Path | None = None) -> dict[str, Any]:
    """Warm all three engines, assert warm, then time 1 cold + ``n_warm`` warm trips."""
    if not input_clip.is_file():
        raise FileNotFoundError(f"input clip missing: {input_clip}")

    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out_wav = Path(tempfile.gettempdir()) / "paaf_roundtrip_out.wav"

    print("[roundtrip] loading STT / LLM / TTS …", flush=True)
    stt = load_stt()
    llm = load_llm()
    tts = load_tts()

    # Cold trip (iteration 0) — also the warmup that lets us ASSERT the stack is wired.
    print("[roundtrip] cold trip (warmup + wiring assertion) …", flush=True)
    cold, cold_art = one_trip(stt, llm, tts, input_clip, out_wav)
    assert cold_art["transcript"], "STT produced an empty transcript — stack not warm/wired"
    assert cold_art["reply"], "LLM produced an empty reply — stack not warm/wired"
    assert cold_art["out_samples"] > 0, "TTS produced no audio — stack not warm/wired"
    print(f"[roundtrip] cold wall={cold['wall']:.2f}s  in='{cold_art['transcript'][:60]}'  "
          f"reply='{cold_art['reply'][:60]}'", flush=True)

    warm: list[dict[str, float]] = []
    last_art = cold_art
    for i in range(n_warm):
        row, last_art = one_trip(stt, llm, tts, input_clip, out_wav)
        warm.append(row)
        print(f"[roundtrip] warm {i + 1}/{n_warm} wall={row['wall']:.2f}s "
              f"stt={row['t_stt']:.2f} llm={row['t_llm']:.2f} tts={row['t_tts']:.2f} "
              f"resid={row['t_unattributed']:.3f}", flush=True)

    budget = build_budget(cold, warm)
    max_rss = _max_rss_bytes()
    max_rss_gb = round(max_rss / 1024 ** 3, 2)
    # Heuristic swap flag: warm p95 wall wildly above p50 hints memory-pressure stalls.
    wall_p50 = statistics.median([w["wall"] for w in warm])
    wall_p95 = _pct([w["wall"] for w in warm], 0.95)
    swap_suspected = wall_p95 > 2.0 * wall_p50 if wall_p50 else False

    result = {
        "input_clip": input_clip.name,
        "stt": {"model": STT_MODEL, "device": STT_DEVICE, "compute_type": STT_COMPUTE_TYPE},
        "llm": {"model": LLM_MODEL, "host": LLM_HOST, "num_predict": LLM_NUM_PREDICT},
        "tts": {"device": TTS_DEVICE, "seed": SEED, "gen_params": GEN_PARAMS,
                "watermark_inside_timed_region": True},
        "hardware": {"unified_memory_gb": 18, "note": "Apple Silicon (D-12): NOT a CUDA measurement"},
        "cold": cold,
        "warm_iterations": warm,
        "budget": budget,
        "warmup_asserted": True,
        "stages_reconstruct_wall": all(stages_reconstruct_wall(r) for r in [cold, *warm]),
        "residual_is_small": all(residual_is_small(r) for r in warm),
        "process_max_rss_bytes": max_rss,
        "process_max_rss_gb": max_rss_gb,
        "process_rss_note": (
            "peak RSS of THIS process only (Whisper + Chatterbox + Dicta); the Ollama "
            "daemon holds qwen3.5:2b in a SEPARATE process not counted here"
        ),
        "swap_suspected": swap_suspected,
        "examples": {"transcript": last_art["transcript"], "reply": last_art["reply"],
                     "out_seconds": last_art["out_seconds"]},
        "started_at": started_at,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text, flush=True)
    if json_out is not None:
        json_out.write_text(text, encoding="utf-8")
        print(f"[roundtrip] wrote {json_out}", flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--n-warm", type=int, default=3, help="warm trips after the cold one")
    ap.add_argument("--input-clip", default=str(DEFAULT_INPUT_CLIP))
    ap.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    args = ap.parse_args(argv)

    run(n_warm=args.n_warm, input_clip=Path(args.input_clip), json_out=Path(args.json_out))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
