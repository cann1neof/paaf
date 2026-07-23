"""GATE 0 — the readiness assertions that must pass before any Hebrew clip is judged.

Marked `slow` for the whole module: these tests load the 1.2 GB dicta ONNX model and the
~3.2 GB Chatterbox checkpoint, and they run real inference. They are excluded from the
quick suite (`-m "not slow"`) and are the gate for the full one.

The module deliberately includes a **negative control**
(`test_the_gate_is_not_vacuous_*`). Without it, every assertion here could pass because
the checks are toothless rather than because the configuration is correct — and a
readiness gate that cannot fail is worse than no gate, because it manufactures confidence.
The negative control reproduces the un-repaired configuration and asserts that the gate
*does* catch it.

Run:
    uv run --python spike/voice/.venv/bin/python pytest spike/voice/test_readiness.py -q
"""

from __future__ import annotations

import logging

import pytest

import gate_readiness as gr

pytestmark = pytest.mark.slow


# --------------------------------------------------------------------------------------
# Fixtures — session-scoped: the weights are loaded once for the whole module
# --------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def dicta_model_path():
    path = gr.resolve_dicta_model_path()
    if path is None:
        pytest.fail(
            "dicta ONNX weights are missing, so Gate 0 cannot be evaluated at all. "
            f"Download {gr.DICTA_MODEL_URL} to {gr.DICTA_MODEL_DEFAULT} "
            f"(or set ${gr.DICTA_MODEL_ENV}). This is a FAILURE, not a skip: skipping "
            "here would let the phase render Hebrew for judgment with the gate unproven."
        )
    return path


@pytest.fixture(scope="session")
def hebrew_ready(dicta_model_path):
    """Applies the repair once and returns the check record."""
    return gr.assert_hebrew_diacritics_active(dicta_model_path)


@pytest.fixture(scope="session")
def tts_and_device(hebrew_ready):
    """Load Chatterbox on the best usable device. Depends on `hebrew_ready` so the
    diacritizer is already seeded before any synthesis happens — the ordering IS the
    gate."""
    tts, result = gr.probe_device()
    if tts is None:
        # Compact summary: the verbatim tracebacks are preserved in the result record and
        # written to raw/voice-provision.md, but dumping them into every dependent test's
        # setup error makes the actual failure unreadable.
        summary = "; ".join(
            f"{a['device']}: {a.get('exception_type')}: {a.get('exception')}"
            for a in result.detail["attempts"]
        )
        pytest.fail(f"no usable inference device -> {summary}")
    return tts, result.detail["usable_device"], result


@pytest.fixture(autouse=True)
def _restore_repair(request, dicta_model_path):
    """Any test that resets the diacritizer must not leak that state into the next test."""
    yield
    if "negative_control" in request.node.name or "vacuous" in request.node.name:
        gr.repair_dicta(dicta_model_path)


# --------------------------------------------------------------------------------------
# Assertion 1 — dicta_onnx imports and MUTATES Hebrew
# --------------------------------------------------------------------------------------


def test_dicta_onnx_is_importable():
    from dicta_onnx import Dicta

    assert callable(Dicta)


def test_chatterbox_native_dicta_construction_is_recorded_either_way():
    """The upstream defect is DATA, not a hidden implementation detail.

    chatterbox 0.1.7 calls `Dicta()` with no arguments while every published dicta-onnx
    release requires `model_path`. This test does not demand a particular answer — it
    demands that the answer is recorded, so that if upstream ever fixes the call, the
    phase notices instead of silently continuing to apply a now-unnecessary repair.
    """
    result = gr.probe_native_dicta_construction()
    assert result.name == "native_dicta_construction"
    assert isinstance(result.ok, bool)
    if not result.ok:
        assert result.detail["exception"], "a failure must carry its verbatim exception"


def test_dicta_mutates_hebrew_consonant_text(hebrew_ready):
    """The hard assert: no consonant-only passthrough."""
    assert hebrew_ready.ok
    assert hebrew_ready.detail["mutated"] is True
    assert hebrew_ready.detail["output"] != hebrew_ready.detail["input"]


def test_diacritized_output_actually_contains_niqqud(hebrew_ready):
    """Stronger than `!=`: the output must contain Hebrew POINT codepoints.

    A mutation that merely stripped whitespace or normalized punctuation would satisfy
    `output != input` while leaving the model a consonant skeleton — exactly the failure
    Gate 0 exists to prevent. Niqqud live in U+05B0–U+05BD, U+05C1, U+05C2, U+05C7.
    """
    out = hebrew_ready.detail["output"]
    niqqud = {*range(0x05B0, 0x05BE), 0x05C1, 0x05C2, 0x05C7}
    found = [c for c in out if ord(c) in niqqud]
    assert found, f"no niqqud codepoints in diacritized output {out!r}"


def test_diacritization_preserves_the_consonant_skeleton(hebrew_ready):
    """Diacritization must ADD vowel points, not rewrite the letters.

    If the consonants changed, the model would be speaking different words and the
    Hebrew verdict would be measuring the diacritizer rather than Chatterbox.
    """
    src = hebrew_ready.detail["input"]
    out = hebrew_ready.detail["output"]
    niqqud = {*range(0x05B0, 0x05BE), 0x05C1, 0x05C2, 0x05C7}
    stripped = "".join(c for c in out if ord(c) not in niqqud)
    assert stripped == src


def test_latin_text_inside_a_mixed_sentence_survives_diacritization(hebrew_ready):
    """Code-switched input is the whole point of the corpus (D-01/D-02).

    A diacritizer that mangled the Latin half would corrupt every mixed sentence before
    Chatterbox ever saw it, and SPIKE-01 would measure that corruption as a code-switching
    failure.
    """
    import chatterbox.models.tokenizers.tokenizer as tok

    src = "הפגישה נקבעה ל-15:00 in the small conference room."
    out = tok.add_hebrew_diacritics(src)
    assert out != src
    assert "in the small conference room." in out


# --------------------------------------------------------------------------------------
# Assertion 3 — russian_text_stresser absence is DETECTED and RECORDED
# --------------------------------------------------------------------------------------


def test_russian_stresser_status_is_detected_and_recorded():
    result = gr.detect_russian_stresser()
    assert result.ok, "the russian stresser status must always be knowable"
    assert "present" in result.detail
    assert result.detail["consequence"], (
        "absence must carry a stated consequence — silently absorbing it is the failure "
        "mode Pitfall 2 warns about"
    )


def test_russian_stresser_is_absent_as_expected_on_a_pip_install():
    """Documents the expected state. If this ever fails, Pitfall 2 has changed and the
    Russian caveat in RESULTS.md must be revisited rather than copied forward."""
    result = gr.detect_russian_stresser()
    assert result.detail["present"] is False
    assert "ModuleNotFoundError" in result.detail["exception"] or "ImportError" in result.detail["exception"]


# --------------------------------------------------------------------------------------
# Assertion 2 — belt and braces: no degradation warning during real synthesis
# --------------------------------------------------------------------------------------


def test_no_degradation_warning_fires_on_a_hebrew_probe_clip(tts_and_device):
    tts, _device, _ = tts_and_device
    result = gr.assert_no_degradation_on_probe_clip(tts)
    assert result.ok
    assert result.detail["degradation_warnings"] == []
    assert result.detail["samples"] > 0, "the probe produced no audio at all"


def test_the_probe_clip_render_is_recorded_with_its_timing(tts_and_device):
    tts, _device, _ = tts_and_device
    result = gr.assert_no_degradation_on_probe_clip(tts)
    assert result.detail["generate_seconds"] > 0


# --------------------------------------------------------------------------------------
# Negative control — the gate must be capable of failing
# --------------------------------------------------------------------------------------


def test_the_gate_is_not_vacuous_negative_control_unrepaired_config(dicta_model_path):
    """Reproduce the un-repaired configuration and assert the gate CATCHES it.

    This is the test that gives every other assertion in this module its meaning. With
    `_dicta` reset, chatterbox falls back to its own broken `Dicta()` call, swallows the
    TypeError, logs a degradation warning and returns the Hebrew unchanged. Both symptoms
    must be observable through `gate_readiness`'s own detectors — if either detector
    missed them, the green gate above would be worthless.
    """
    import chatterbox.models.tokenizers.tokenizer as tok

    gr.reset_dicta()
    with gr.capture_logs() as records:
        out = tok.add_hebrew_diacritics(gr.HEBREW_PROBE_TEXT)

    assert out == gr.HEBREW_PROBE_TEXT, (
        "expected the UNREPAIRED path to pass Hebrew through unchanged; if it mutated, "
        "upstream has fixed the defect and the repair should be retired"
    )
    bad = gr.degradation_records(records)
    assert bad, "the degradation detector failed to see an active degradation path"
    assert any(r.levelno >= logging.WARNING for r in bad)


def test_the_hard_assert_raises_gate_failure_when_weights_are_missing(monkeypatch):
    """`repair_dicta` must fail LOUDLY, with instructions, rather than degrade."""
    monkeypatch.setattr(gr, "resolve_dicta_model_path", lambda *a, **k: None)
    with pytest.raises(gr.GateFailure) as exc:
        gr.repair_dicta()
    assert gr.DICTA_MODEL_URL in str(exc.value)


def test_unrelated_third_party_warnings_do_not_fail_the_gate():
    """A gate that trips on noise gets ignored, which is the same as not having one.

    The huggingface_hub "set a HF_TOKEN" notice is emitted on every unauthenticated
    download and is EXPECTED here — this project deliberately sets no token. It must be
    recorded but must never be read as a chatterbox degradation.
    """
    logger = logging.getLogger("huggingface_hub.utils._http")
    with gr.capture_logs() as records:
        logger.warning("Warning: You are sending unauthenticated requests to the HF Hub.")
    assert gr.degradation_records(records) == []
    assert any("unauthenticated" in r.getMessage() for r in gr.other_warnings(records))


# --------------------------------------------------------------------------------------
# Assertion 4/5 — device and seed are RECORDED (their values are findings, not pass/fail)
# --------------------------------------------------------------------------------------


def test_the_usable_device_is_probed_and_recorded(tts_and_device):
    _tts, device, result = tts_and_device
    assert device in gr.DEVICE_CANDIDATES
    attempts = result.detail["attempts"]
    assert attempts, "the probe must record what it tried, not just what worked"
    # Every failed attempt must carry its exception verbatim — per D-11/D-12 an MPS
    # failure is a legitimate, decision-relevant measurement for the hardware purchase,
    # so losing the text would destroy the finding.
    for a in attempts:
        if not a.get("generated"):
            assert a.get("exception"), f"failed attempt for {a['device']} lost its exception"


def test_mps_is_probed_with_the_string_not_a_torch_device(tts_and_device):
    """Pitfall 4: `from_pretrained` compares `device == "mps"` as a STRING despite its
    torch.device type hint. Passing torch.device("mps") skips the availability check and
    the CPU fallback entirely."""
    _tts, _device, result = tts_and_device
    devices = [a["device"] for a in result.detail["attempts"]]
    assert "mps" in devices
    assert all(isinstance(d, str) for d in devices)


def test_seed_reproducibility_is_measured_and_recorded(tts_and_device):
    """Open Question 2 / assumption A6. Either answer is acceptable; NOT knowing is not.

    A negative result does not fail this test — it softens D-07's re-run-and-diff promise
    to a qualitative comparison, which is a finding for Phase 7 to inherit.
    """
    tts, device, _ = tts_and_device
    result = gr.check_seed_reproducibility(tts, device=device)
    assert result.ok
    assert result.detail["seed"] == gr.GATE_SEED
    assert isinstance(result.detail["bitwise_identical"], bool)
    assert result.detail["consequence"]
