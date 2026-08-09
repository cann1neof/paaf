# SPDX-License-Identifier: Apache-2.0
"""Silero VAD engine adapter implementing VAD port protocol (VOICE-08)."""

import struct
from typing import Any

from paaf_voice.engines.registry import register_vad_engine
from paaf_voice.ports import VAD, AudioFrame, VADResult


@register_vad_engine("silero")
class SileroVADEngine(VAD):
    """Voice Activity Detection engine adapter wrapping Silero VAD (ONNX).

    Supports continuous sensing with dynamic dual thresholds:
    - speech_threshold_idle (default 0.50): sensitivity when idle.
    - speech_threshold_playback (default 0.65): higher threshold during active playback
      to prevent acoustic echo/speaker bleed false triggers.
    """

    def __init__(
        self,
        model_path: str | None = None,
        speech_threshold_idle: float = 0.50,
        speech_threshold_playback: float = 0.65,
        sample_rate: int = 16000,
        model: Any = None,
    ) -> None:
        self.model_path = model_path
        self.speech_threshold_idle = float(speech_threshold_idle)
        self.speech_threshold_playback = float(speech_threshold_playback)
        self.sample_rate = sample_rate
        self._model = model
        self._playback_active = False
        self._is_warmed_up = False

        self._h: Any = None
        self._c: Any = None
        self._state: Any = None
        self.reset_states()

    def set_playback_active(self, active: bool) -> None:
        """Toggle active playback state to switch between idle and playback thresholds."""
        self._playback_active = bool(active)

    @property
    def current_threshold(self) -> float:
        """Return currently active speech detection threshold based on playback state."""
        return (
            self.speech_threshold_playback
            if self._playback_active
            else self.speech_threshold_idle
        )

    def reset_states(self) -> None:
        """Reset internal recurrent hidden state tensors."""
        try:
            import numpy as np

            self._h = np.zeros((2, 1, 64), dtype=np.float32)
            self._c = np.zeros((2, 1, 64), dtype=np.float32)
            self._state = np.zeros((2, 1, 128), dtype=np.float32)
        except ImportError:
            self._h = None
            self._c = None
            self._state = None

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            import onnxruntime as ort
        except ImportError as err:
            raise ImportError(
                "onnxruntime package is required for SileroVADEngine. "
                "Install it using `pip install onnxruntime`."
            ) from err

        if not self.model_path:
            raise ValueError(
                "model_path or pre-instantiated model is required for SileroVADEngine."
            )

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1

        self._model = ort.InferenceSession(self.model_path, opts)
        return self._model

    def warmup(self) -> None:
        """Pre-load ONNX model session, reset states, and run a 20ms silence pass."""
        _ = self._ensure_model()
        self.reset_states()

        # 20ms silence frame (320 samples @ 16kHz)
        silence_frame = AudioFrame(
            data=b"\x00" * 640,
            sample_rate=self.sample_rate,
            channels=1,
            sample_width=2,
        )
        try:
            self.process_frame(silence_frame)
        except Exception:  # noqa: BLE001, S110
            pass
        self._is_warmed_up = True

    def process_frame(self, frame: AudioFrame) -> VADResult:
        """Process an audio frame for speech activity detection."""
        if not frame.data:
            return VADResult(is_speech=False, confidence=0.0)

        model = self._ensure_model()
        audio_data = _pcm16_to_float32(frame.data)

        prob = 0.0

        if hasattr(model, "run"):
            # Check input names for ONNX session
            input_names = []
            if hasattr(model, "get_inputs"):
                try:
                    input_names = [inp.name for inp in model.get_inputs()]
                except Exception:  # noqa: BLE001
                    input_names = []

            try:
                import numpy as np

                sr_val = np.int64(self.sample_rate)
                # Reshape audio to (1, N)
                if isinstance(audio_data, np.ndarray):
                    audio_tensor = audio_data.reshape(1, -1)
                else:
                    audio_tensor = np.array([audio_data], dtype=np.float32)

                if "state" in input_names:
                    # Silero VAD v5
                    if self._state is None:
                        self._state = np.zeros((2, 1, 128), dtype=np.float32)
                    inputs = {
                        "input": audio_tensor,
                        "state": self._state,
                        "sr": sr_val,
                    }
                    outputs = model.run(None, inputs)
                    prob = float(outputs[0].flat[0])
                    if len(outputs) > 1:
                        self._state = outputs[1]
                elif "h" in input_names or "c" in input_names:
                    # Silero VAD v4
                    if self._h is None:
                        self._h = np.zeros((2, 1, 64), dtype=np.float32)
                    if self._c is None:
                        self._c = np.zeros((2, 1, 64), dtype=np.float32)
                    inputs = {
                        "input": audio_tensor,
                        "sr": sr_val,
                        "h": self._h,
                        "c": self._c,
                    }
                    outputs = model.run(None, inputs)
                    prob = float(outputs[0].flat[0])
                    if len(outputs) > 2:
                        self._h = outputs[1]
                        self._c = outputs[2]
                else:
                    # Generic mock / model run
                    inputs = {"input": audio_tensor}
                    outputs = model.run(None, inputs)
                    if isinstance(outputs, (list, tuple)) and len(outputs) > 0:
                        res = outputs[0]
                        prob = float(res.flat[0]) if hasattr(res, "flat") else float(res)
                    else:
                        prob = float(outputs)
            except Exception:  # noqa: BLE001
                # Mock run fallback if mock ignores parameter names
                res = model.run(None, {"input": audio_data})
                if isinstance(res, (list, tuple)) and len(res) > 0:
                    val = res[0]
                    prob = float(val.flat[0]) if hasattr(val, "flat") else float(val)
                else:
                    prob = float(res)
        elif callable(model):
            res = model(audio_data)
            prob = float(res)
        elif hasattr(model, "prediction"):
            prob = float(model.prediction)

        is_speech = prob >= self.current_threshold
        return VADResult(is_speech=is_speech, confidence=prob)


def _pcm16_to_float32(pcm_bytes: bytes) -> Any:
    """Convert PCM 16-bit mono bytes to normalized float32 (-1.0 to 1.0)."""
    try:
        import numpy as np

        return np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    except ImportError:
        num_samples = len(pcm_bytes) // 2
        if num_samples == 0:
            return []
        fmt = f"<{num_samples}h"
        ints = struct.unpack(fmt, pcm_bytes[: num_samples * 2])
        return [val / 32768.0 for val in ints]
