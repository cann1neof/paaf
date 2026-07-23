"""GATE 0 — engine-readiness gate for the voice half of Phase 1.

Nothing in this phase that produces Hebrew audio for human judgment may run until this
gate is green. Chatterbox degrades to a ``logger.warning`` instead of raising when its
language-preprocessing helpers are unavailable, so a broken configuration produces audio
that *looks* fine and sounds wrong for a reason that has nothing to do with the model.
Judging Hebrew against such a configuration would burn the single irreplaceable resource
in this phase: a first, unprimed native-ear impression (D-13/D-14).

What this module asserts, in order:

1. ``from dicta_onnx import Dicta`` succeeds and a *usable* ``Dicta`` instance MUTATES a
   Hebrew consonant string. Hard ``assert`` — not a soft check.
2. Belt and braces: one short Hebrew probe clip is rendered through Chatterbox with the
   runtime logger captured, and the gate fails if any chatterbox degradation warning
   fires (see ``DEGRADATION_MARKERS`` — the warning *text* is read off the live logger,
   never hard-coded here, so this module cannot go stale against upstream wording).
3. ``russian_text_stresser`` absence is DETECTED and RECORDED, never silently absorbed.
4. The usable inference device is probed by passing the **string** ``"mps"``, catching
   any exception verbatim as data.
5. Seed reproducibility is measured, because D-07 promises Phase 7 can re-run and diff.

⚠️ UPSTREAM DEFECT THIS GATE EXISTS TO CATCH (discovered by this gate, 2026-07-23)
-----------------------------------------------------------------------------------
``chatterbox-tts==0.1.7`` constructs the diacritizer as ``Dicta()`` with no arguments,
but ``Dicta.__init__(self, model_path: str)`` has required ``model_path`` in **every**
published dicta-onnx release (1.0.0 … 1.0.9). The resulting ``TypeError`` is swallowed by
chatterbox's ``except Exception`` arm, which logs a warning and returns the text
unchanged. So ``pip install dicta-onnx`` alone does **not** fix Pitfall 1 — it only
changes *which* warning fires while Hebrew still reaches the model as a consonant
skeleton. See ``repair_dicta()``: the repair is to build ``Dicta(model_path)`` ourselves
and seed the module-level global chatterbox caches, which is the smallest change that
makes the measured pipeline the intended one.

Because of that defect this module distinguishes two configurations, and callers must say
which one they mean:

``CONFIG_DEFAULT``   what a user gets from ``pip install chatterbox-tts dicta-onnx``:
                     Hebrew is synthesized WITHOUT diacritics. Gate 0 is RED here, and
                     that redness is itself a finding worth reporting (D-05).
``CONFIG_REPAIRED``  the defect worked around by supplying the ONNX model path. Hebrew is
                     synthesized WITH diacritics. Gate 0 can go GREEN here, and this is
                     the configuration SPIKE-02's verdict should be attributed to.

Throwaway spike code (SC#5): this file dies with ``spike/``. Findings survive in
``.planning/phases/01-spike-gate/raw/voice-provision.md``.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import gc
import logging
import os
import platform
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Iterator

# --------------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------------

CONFIG_DEFAULT = "default"
CONFIG_REPAIRED = "repaired"

#: Logger tree Chatterbox emits its degradation warnings under. Anything outside this
#: tree (e.g. huggingface_hub's "set a HF_TOKEN" notice) is recorded but never fails the
#: gate — a false gate failure is as damaging as a false pass, because it trains the
#: reader to ignore the gate.
CHATTERBOX_LOGGER = "chatterbox"

#: Generic *shapes* of a silent-degradation log line. Deliberately NOT the literal
#: upstream strings: this module must keep working if Resemble rewords the warning, and
#: the actual text is captured from the live logger and reported verbatim instead.
DEGRADATION_MARKERS = ("not available", "skipped", "failed")

#: Short Hebrew consonant string. Correct diacritization yields "שְׁלוֹם עוֹלָם".
HEBREW_PROBE_TEXT = "שלום עולם"

#: One short Hebrew sentence to synthesize for the belt-and-braces log check. Kept short
#: on purpose: this gate must be cheap enough that nobody is tempted to skip it.
HEBREW_PROBE_CLIP = "שלום, מה שלומך היום"

#: dicta-onnx ships no weights. The full fp32 export is used rather than the int8 one so
#: that quantization artifacts in *diacritization* can never be misread as a Chatterbox
#: Hebrew failure — the same reasoning RESEARCH uses to prefer whisper large-v3 over the
#: community turbo conversion.
DICTA_MODEL_ENV = "PAAF_DICTA_MODEL"
DICTA_MODEL_DEFAULT = Path(__file__).resolve().parent / ".models" / "dicta-1.0.onnx"
DICTA_MODEL_URL = (
    "https://github.com/thewh1teagle/dicta-onnx/releases/download/"
    "model-files-v1.0/dicta-1.0.onnx"
)

#: Fixed seed for the reproducibility probe (Pitfall 6). Recorded, never implicit.
GATE_SEED = 1234

#: Device candidates in preference order. The STRING "mps" is mandatory: chatterbox's
#: from_pretrained does `device == "mps"`, a *string* comparison, despite its
#: torch.device type hint — torch.device("mps") silently skips the availability check
#: and the CPU fallback (Pitfall 4).
DEVICE_CANDIDATES = ("mps", "cpu")


# --------------------------------------------------------------------------------------
# Result records
# --------------------------------------------------------------------------------------


@dataclasses.dataclass
class CheckResult:
    """One readiness check. ``ok`` False means Gate 0 is red for that check."""

    name: str
    ok: bool
    detail: dict[str, Any] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, **self.detail}


class GateFailure(AssertionError):
    """Raised when a hard readiness assertion fails. Loud by construction."""


# --------------------------------------------------------------------------------------
# Log capture
# --------------------------------------------------------------------------------------


class _RecordingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        self.records.append(record)


@contextlib.contextmanager
def capture_logs() -> Iterator[list[logging.LogRecord]]:
    """Capture every log record emitted anywhere while the block runs.

    Attached to the root logger *and* to the chatterbox logger explicitly, because a
    library that sets ``propagate = False`` would otherwise be invisible to a root-only
    handler — which is exactly the failure mode this gate must not have.
    """
    handler = _RecordingHandler()
    root = logging.getLogger()
    cb = logging.getLogger(CHATTERBOX_LOGGER)

    prev_root_level, prev_cb_level = root.level, cb.level
    root.addHandler(handler)
    cb.addHandler(handler)
    root.setLevel(logging.DEBUG)
    cb.setLevel(logging.DEBUG)
    try:
        yield handler.records
    finally:
        root.removeHandler(handler)
        cb.removeHandler(handler)
        root.setLevel(prev_root_level)
        cb.setLevel(prev_cb_level)


def degradation_records(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
    """Records that indicate an active silent-degradation path in Chatterbox.

    Scoped to the chatterbox logger tree: an unrelated third-party warning must not fail
    the gate, and the "unauthenticated requests to the HF Hub" notice in particular is
    *expected* here — this project deliberately sets no ``HF_TOKEN``.
    """
    out = []
    for r in records:
        if r.levelno < logging.WARNING:
            continue
        if not (r.name == CHATTERBOX_LOGGER or r.name.startswith(CHATTERBOX_LOGGER + ".")):
            continue
        msg = r.getMessage().lower()
        if any(m in msg for m in DEGRADATION_MARKERS):
            out.append(r)
    return out


def other_warnings(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
    """Warnings that are NOT gate failures, kept so they are reported rather than lost."""
    degraded = set(id(r) for r in degradation_records(records))
    return [r for r in records if r.levelno >= logging.WARNING and id(r) not in degraded]


# --------------------------------------------------------------------------------------
# Check 1 — Hebrew diacritics
# --------------------------------------------------------------------------------------


def resolve_dicta_model_path(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """Locate the dicta ONNX weights, or return None if they are not on disk."""
    for candidate in (explicit, os.environ.get(DICTA_MODEL_ENV), DICTA_MODEL_DEFAULT):
        if not candidate:
            continue
        p = Path(candidate).expanduser()
        if p.is_file():
            return p.resolve()
    return None


def probe_native_dicta_construction() -> CheckResult:
    """Record whether chatterbox's own ``Dicta()`` call works, WITHOUT repairing it.

    This is the finding, not the fix. It is expected to be False on
    chatterbox-tts 0.1.7 + dicta-onnx 1.0.9, and recording it is how the phase reports
    what a plain ``pip install`` actually gives a user.
    """
    try:
        from dicta_onnx import Dicta
    except ImportError as e:
        return CheckResult(
            "native_dicta_construction",
            ok=False,
            detail={"stage": "import", "exception": f"{type(e).__name__}: {e}"},
        )
    try:
        Dicta()  # exactly the call chatterbox makes
        return CheckResult("native_dicta_construction", ok=True, detail={"stage": "construct"})
    except Exception as e:  # noqa: BLE001 — the exception IS the datum
        return CheckResult(
            "native_dicta_construction",
            ok=False,
            detail={"stage": "construct", "exception": f"{type(e).__name__}: {e}"},
        )


def repair_dicta(model_path: str | os.PathLike[str] | None = None) -> Any:
    """Work around the upstream defect by seeding chatterbox's cached diacritizer.

    ``add_hebrew_diacritics`` only constructs ``Dicta()`` when its module-level ``_dicta``
    global is None, so installing a correctly-constructed instance there bypasses the
    broken zero-arg call and leaves every other line of the upstream code path untouched.
    That "leaves the rest untouched" property is the point: the goal is to measure
    Chatterbox's real Hebrew pipeline, not a reimplementation of it.
    """
    from dicta_onnx import Dicta
    import chatterbox.models.tokenizers.tokenizer as tok

    path = resolve_dicta_model_path(model_path)
    if path is None:
        raise GateFailure(
            "dicta ONNX weights not found. dicta-onnx ships no weights and chatterbox "
            f"cannot supply the path itself. Download {DICTA_MODEL_URL} to "
            f"{DICTA_MODEL_DEFAULT} (or set ${DICTA_MODEL_ENV}), then re-run Gate 0."
        )
    tok._dicta = Dicta(str(path))
    return tok._dicta


def reset_dicta() -> None:
    """Restore the un-repaired state, so CONFIG_DEFAULT can be measured honestly."""
    import chatterbox.models.tokenizers.tokenizer as tok

    tok._dicta = None


def assert_hebrew_diacritics_active(
    model_path: str | os.PathLike[str] | None = None,
    text: str = HEBREW_PROBE_TEXT,
) -> CheckResult:
    """HARD assertion: Hebrew input is MUTATED, i.e. no consonant-only passthrough.

    Raises :class:`GateFailure` rather than returning a falsy result, because the whole
    value of this gate is that it cannot be walked past.
    """
    import chatterbox.models.tokenizers.tokenizer as tok

    repair_dicta(model_path)

    with capture_logs() as records:
        out = tok.add_hebrew_diacritics(text)

    if out == text:
        raise GateFailure(
            "Dicta loaded but returned Hebrew text unchanged — Hebrew would be "
            f"synthesized from a consonant skeleton. input={text!r}"
        )
    bad = degradation_records(records)
    if bad:
        raise GateFailure(
            "the diacritics-skipped degradation path is active per Pitfall 1: "
            f"{[r.getMessage() for r in bad]}"
        )

    return CheckResult(
        "hebrew_diacritics_active",
        ok=True,
        detail={
            "input": text,
            "output": out,
            "mutated": True,
            "model_path": str(resolve_dicta_model_path(model_path)),
        },
    )


# --------------------------------------------------------------------------------------
# Check 3 — Russian stress labeling
# --------------------------------------------------------------------------------------


def detect_russian_stresser() -> CheckResult:
    """Detect whether Russian stress labeling is available. Absence is EXPECTED.

    ``russian_text_stresser`` 404s on PyPI under every name variant, so this cannot be
    fixed by an install. Per D-05 it is recorded as a real property of what users get —
    Russian in this phase is measured WITHOUT stress labeling — rather than absorbed.
    """
    try:
        from russian_text_stresser.text_stresser import RussianTextStresser  # noqa: F401
    except ImportError as e:
        return CheckResult(
            "russian_stresser",
            ok=True,  # ok == "we know the answer and recorded it", not "it is present"
            detail={
                "present": False,
                "exception": f"{type(e).__name__}: {e}",
                "consequence": (
                    "Russian is measured WITHOUT stress labeling. This is what a user "
                    "gets from a default install; it is not fixable by pip (permanent "
                    "PyPI 404). Carry this caveat into any D-20 Russian spot-check."
                ),
            },
        )
    return CheckResult(
        "russian_stresser",
        ok=True,
        detail={
            "present": True,
            "consequence": (
                "UNEXPECTED: russian_text_stresser resolved. Pitfall 2 no longer applies "
                "and Russian is measured WITH stress labeling — record which build."
            ),
        },
    )


# --------------------------------------------------------------------------------------
# Check 4 — device probe
# --------------------------------------------------------------------------------------


def _free(obj: Any = None) -> None:
    import torch

    del obj
    gc.collect()
    with contextlib.suppress(Exception):
        torch.mps.empty_cache()


def synthesize(tts: Any, text: str, language_id: str | None, seed: int = GATE_SEED):
    """One seeded generation. Returns ``(waveform, seconds)``.

    ``torch.manual_seed`` is called immediately before *each* generate (not once per
    process): batching and subprocess boundaries would otherwise shift the RNG stream and
    make the reproducibility answer meaningless (Pitfall 6).
    """
    import torch

    torch.manual_seed(seed)
    t0 = time.perf_counter()
    wav = tts.generate(text, language_id=language_id)
    return wav, time.perf_counter() - t0


def probe_device(
    candidates: tuple[str, ...] = DEVICE_CANDIDATES,
    probe_text: str = HEBREW_PROBE_CLIP,
    language_id: str = "he",
) -> tuple[Any, CheckResult]:
    """Find the usable inference device. Returns ``(loaded_tts, CheckResult)``.

    An MPS failure is a VALID recorded result (D-11/D-12) and directly relevant to the
    deferred hardware purchase — it is never a phase blocker. Construction alone is not
    enough of a probe: the documented Chatterbox MPS failures (``Placeholder storage has
    not been allocated on MPS device!``, float64 unsupported) surface during *inference*,
    so each candidate must actually generate before it is believed.
    """
    from chatterbox import ChatterboxMultilingualTTS

    attempts: list[dict[str, Any]] = []
    for dev in candidates:
        record: dict[str, Any] = {"device": dev}
        tts = None
        try:
            tts = ChatterboxMultilingualTTS.from_pretrained(device=dev)  # STRING, Pitfall 4
            record["constructed"] = True
            _, secs = synthesize(tts, probe_text, language_id)
            record["generated"] = True
            record["generate_seconds"] = round(secs, 3)
            attempts.append(record)
            return tts, CheckResult(
                "device_probe",
                ok=True,
                detail={"usable_device": dev, "attempts": attempts},
            )
        except Exception as e:  # noqa: BLE001 — the exception text IS the measurement
            record["constructed"] = record.get("constructed", False)
            record["generated"] = False
            record["exception_type"] = type(e).__name__
            record["exception"] = str(e)
            record["traceback_tail"] = "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )[-1500:]
            attempts.append(record)
            _free(tts)

    return None, CheckResult(
        "device_probe", ok=False, detail={"usable_device": None, "attempts": attempts}
    )


# --------------------------------------------------------------------------------------
# Check 2 — belt-and-braces: no degradation warning during real synthesis
# --------------------------------------------------------------------------------------


def assert_no_degradation_on_probe_clip(
    tts: Any, text: str = HEBREW_PROBE_CLIP, language_id: str = "he"
) -> CheckResult:
    """Render ONE short Hebrew probe clip and fail if any chatterbox warning fires.

    Check 1 proves the diacritizer works when called directly. This proves Chatterbox
    actually *reaches* it during a real ``generate()`` — the two are not the same claim,
    and only the second one is what SPIKE-02 will hear.
    """
    with capture_logs() as records:
        wav, secs = synthesize(tts, text, language_id)

    bad = degradation_records(records)
    if bad:
        raise GateFailure(
            "chatterbox degradation warning fired while synthesizing the Hebrew probe "
            f"clip: {[(r.name, r.getMessage()) for r in bad]}"
        )

    return CheckResult(
        "no_degradation_on_probe_clip",
        ok=True,
        detail={
            "text": text,
            "language_id": language_id,
            "generate_seconds": round(secs, 3),
            "samples": int(wav.numel()),
            "degradation_warnings": [],
            "other_warnings": sorted({f"{r.name}: {r.getMessage()}" for r in other_warnings(records)}),
        },
    )


# --------------------------------------------------------------------------------------
# Check 5 — seed reproducibility
# --------------------------------------------------------------------------------------


def check_seed_reproducibility(
    tts: Any,
    device: str,
    text: str = HEBREW_PROBE_CLIP,
    language_id: str = "he",
    seed: int = GATE_SEED,
) -> CheckResult:
    """Render the same sentence twice under the same seed and compare the waveforms.

    Open Question 2. If they differ, D-07's "Phase 7 re-runs and diffs against Phase 1"
    promise softens to a qualitative comparison — far better discovered now than in
    Phase 7. Not a gate failure either way: this check reports, it does not block.
    """
    import torch

    a, secs_a = synthesize(tts, text, language_id, seed=seed)
    b, secs_b = synthesize(tts, text, language_id, seed=seed)

    a_c, b_c = a.detach().float().cpu(), b.detach().float().cpu()
    same_shape = tuple(a_c.shape) == tuple(b_c.shape)
    if same_shape:
        identical = bool(torch.equal(a_c, b_c))
        max_abs_diff = float((a_c - b_c).abs().max())
        allclose = bool(torch.allclose(a_c, b_c, atol=1e-6))
    else:
        identical, max_abs_diff, allclose = False, float("nan"), False

    return CheckResult(
        "seed_reproducibility",
        ok=True,  # informational: a negative answer is a finding, not a gate failure
        detail={
            "seed": seed,
            "device": device,
            "text": text,
            "language_id": language_id,
            "shape_a": tuple(a_c.shape),
            "shape_b": tuple(b_c.shape),
            "same_shape": same_shape,
            "bitwise_identical": identical,
            "allclose_atol_1e-6": allclose,
            "max_abs_diff": max_abs_diff,
            "generate_seconds": [round(secs_a, 3), round(secs_b, 3)],
            "consequence": (
                "D-07's re-run-and-diff promise holds on this backend."
                if identical
                else "D-07's re-run-and-diff promise softens to a QUALITATIVE comparison "
                "on this backend; Phase 7 cannot assert bitwise equality."
            ),
        },
    )


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------


def environment_record() -> dict[str, Any]:
    import torch

    import chatterbox

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "torch": torch.__version__,
        "mps_is_built": bool(torch.backends.mps.is_built()),
        "mps_is_available": bool(torch.backends.mps.is_available()),
        "chatterbox": chatterbox.__version__,
        "hf_token_set": bool(os.environ.get("HF_TOKEN")),
    }


def run_gate(model_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Run every readiness check. Returns a result dict; raises GateFailure when red."""
    results: list[CheckResult] = []

    reset_dicta()
    native = probe_native_dicta_construction()
    results.append(native)

    results.append(assert_hebrew_diacritics_active(model_path))
    results.append(detect_russian_stresser())

    tts, device_result = probe_device()
    results.append(device_result)
    if tts is None:
        raise GateFailure(
            "no usable inference device: every candidate failed. "
            f"attempts={device_result.detail['attempts']}"
        )
    device = device_result.detail["usable_device"]

    results.append(assert_no_degradation_on_probe_clip(tts))
    results.append(check_seed_reproducibility(tts, device=device))

    green = all(r.ok for r in results if r.name != "native_dicta_construction")
    return {
        "gate": "GREEN" if green else "RED",
        "configuration": CONFIG_REPAIRED,
        "environment": environment_record(),
        "checks": [r.as_dict() for r in results],
    }


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------


def render_report(result: dict[str, Any]) -> str:
    """Render the gate outcome as the markdown appended to raw/voice-provision.md."""
    by_name = {c["name"]: c for c in result["checks"]}
    env = result["environment"]
    lines: list[str] = []
    add = lines.append

    add("")
    add("## Task 2 — GATE 0 readiness outcomes")
    add("")
    add(f"**GATE 0: {result['gate']}** (configuration: `{result['configuration']}`)")
    add("")
    add("| Environment | Value |")
    add("|---|---|")
    for k, v in env.items():
        add(f"| `{k}` | `{v}` |")
    add("")

    n = by_name.get("native_dicta_construction", {})
    add("### Upstream defect — chatterbox's own `Dicta()` call")
    add("")
    add(f"- chatterbox's zero-arg `Dicta()` works: **{n.get('ok')}**")
    if n.get("exception"):
        add(f"- exception (verbatim): `{n['exception']}`")
    add("")

    h = by_name.get("hebrew_diacritics_active", {})
    add("### Check 1 — Hebrew diacritics MUTATE the input (hard assert)")
    add("")
    add(f"- input : `{h.get('input')}`")
    add(f"- output: `{h.get('output')}`")
    add(f"- mutated: **{h.get('mutated')}**")
    add(f"- dicta model: `{h.get('model_path')}`")
    add("")

    p = by_name.get("no_degradation_on_probe_clip", {})
    add("### Check 2 — no degradation warning during a real Hebrew probe render")
    add("")
    add(f"- probe text: `{p.get('text')}` (`language_id={p.get('language_id')}`)")
    add(f"- generate: **{p.get('generate_seconds')} s**, {p.get('samples')} samples")
    add(f"- chatterbox degradation warnings: **{p.get('degradation_warnings')}**")
    for w in p.get("other_warnings") or []:
        add(f"- non-blocking warning (recorded, not a gate failure): `{w}`")
    add("")

    r = by_name.get("russian_stresser", {})
    add("### Check 3 — Russian stress labeling")
    add("")
    add(f"- `russian_text_stresser` present: **{r.get('present')}**")
    if r.get("exception"):
        add(f"- exception (verbatim): `{r['exception']}`")
    add(f"- consequence: {r.get('consequence')}")
    add("")

    d = by_name.get("device_probe", {})
    add("### Check 4 — usable inference device")
    add("")
    add(f"- **usable device: `{d.get('usable_device')}`**")
    add("")
    for a in d.get("attempts") or []:
        add(f"- `{a['device']}`: constructed={a.get('constructed')} generated={a.get('generated')}"
            + (f" in {a['generate_seconds']} s" if a.get("generate_seconds") is not None else ""))
        if a.get("exception"):
            add(f"  - `{a['exception_type']}` verbatim: `{a['exception']}`")
    add("")

    s = by_name.get("seed_reproducibility", {})
    add("### Check 5 — seed reproducibility (Open Question 2)")
    add("")
    add(f"- seed `{s.get('seed')}` on `{s.get('device')}`, same sentence rendered twice")
    add(f"- shapes: `{s.get('shape_a')}` vs `{s.get('shape_b')}` (same_shape={s.get('same_shape')})")
    add(f"- **bitwise identical: {s.get('bitwise_identical')}**")
    add(f"- allclose(atol=1e-6): {s.get('allclose_atol_1e-6')}; max |diff|: {s.get('max_abs_diff')}")
    add(f"- generate times: {s.get('generate_seconds')} s")
    add(f"- consequence: {s.get('consequence')}")
    add("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run GATE 0 and record the outcomes.")
    ap.add_argument("--dicta-model", default=None, help="path to dicta-1.0.onnx")
    ap.add_argument("--append", default=None, help="markdown file to append the report to")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        result = run_gate(args.dicta_model)
    except GateFailure as e:
        print(f"GATE 0: RED\n{e}", file=sys.stderr)
        return 1

    report = render_report(result)
    print(report)
    if args.append:
        p = Path(args.append)
        p.write_text(p.read_text().rstrip() + "\n" + report + "\n")
        print(f"appended to {p}", file=sys.stderr)
    return 0 if result["gate"] == "GREEN" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
