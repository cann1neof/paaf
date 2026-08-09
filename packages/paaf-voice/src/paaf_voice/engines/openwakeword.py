# SPDX-License-Identifier: Apache-2.0
"""OpenWakeWord engine adapter implementing WakeWord port protocol (VOICE-07)."""

import struct
from typing import Any

from paaf_voice.engines.registry import register_wake_engine
from paaf_voice.ports import AudioFrame, WakeWord, WakeWordResult


@register_wake_engine("openwakeword")
class OpenWakeWordEngine(WakeWord):
    """Wake word detection engine adapter wrapping openWakeWord (ONNX)."""

    def __init__(
        self,
        model_path_or_name: str = "hey_jarvis",
        threshold: float = 0.5,
        model: Any = None,
    ) -> None:
        self.model_path_or_name = model_path_or_name
        self.threshold = float(threshold)
        self._model = model
        self._is_warmed_up = False

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from openwakeword.model import Model
        except ImportError as err:
            raise ImportError(
                "openwakeword package is required for OpenWakeWordEngine. "
                "Install it using `pip install openwakeword`."
            ) from err

        try:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
        except ImportError:
            opts = None

        # Initialize openWakeWord Model with single-threaded ONNX session options if possible
        if opts is not None:
            self._model = Model(
                wakeword_models=[self.model_path_or_name],
                inference_framework="onnx",
                sess_options=opts,
            )
        else:
            self._model = Model(
                wakeword_models=[self.model_path_or_name],
                inference_framework="onnx",
            )
        return self._model

    def warmup(self) -> None:
        """Pre-load ONNX model weights and run a 20ms silence dummy pass."""
        _ = self._ensure_model()
        # 20ms of silence at 16kHz 16-bit mono = 320 samples = 640 bytes
        silence_frame = AudioFrame(
            data=b"\x00" * 640,
            sample_rate=16000,
            channels=1,
            sample_width=2,
        )
        try:
            self.detect(silence_frame)
        except Exception:  # noqa: BLE001, S110
            pass
        self._is_warmed_up = True

    def detect(self, frame: AudioFrame) -> WakeWordResult:
        """Process an audio frame for wake word detection."""
        if not frame.data:
            return WakeWordResult(detected=False, keyword=None, confidence=0.0)

        model = self._ensure_model()
        audio_data = _pcm16_to_int16_array(frame.data)

        # Call predict on model
        if hasattr(model, "predict"):
            predictions = model.predict(audio_data)
        elif callable(model):
            predictions = model(audio_data)
        else:
            predictions = getattr(model, "prediction", {})

        keyword, conf = _parse_predictions(predictions, self.model_path_or_name)
        detected = conf >= self.threshold
        return WakeWordResult(
            detected=detected,
            keyword=keyword,
            confidence=conf,
        )


def _pcm16_to_int16_array(pcm_bytes: bytes) -> Any:
    """Convert PCM 16-bit mono bytes to int16 numpy array or list."""
    try:
        import numpy as np

        return np.frombuffer(pcm_bytes, dtype=np.int16)
    except ImportError:
        num_samples = len(pcm_bytes) // 2
        if num_samples == 0:
            return []
        fmt = f"<{num_samples}h"
        return list(struct.unpack(fmt, pcm_bytes[: num_samples * 2]))


def _parse_predictions(predictions: Any, target_keyword: str) -> tuple[str | None, float]:
    """Extract keyword name and confidence score from openWakeWord prediction output."""
    if isinstance(predictions, dict):
        if not predictions:
            return None, 0.0
        # If target_keyword is in prediction keys or matches a key suffix
        if target_keyword in predictions:
            return target_keyword, float(predictions[target_keyword])
        for k, v in predictions.items():
            if target_keyword in k or k in target_keyword:
                return str(k), float(v)
        # Fall back to key with highest prediction score
        best_key, best_score = max(predictions.items(), key=lambda item: item[1])
        return str(best_key), float(best_score)
    elif isinstance(predictions, (int, float)):
        return target_keyword, float(predictions)
    elif isinstance(predictions, (tuple, list)) and len(predictions) > 0:
        return target_keyword, float(predictions[0])
    return target_keyword, 0.0
