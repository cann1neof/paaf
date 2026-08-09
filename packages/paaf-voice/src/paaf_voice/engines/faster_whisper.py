# SPDX-License-Identifier: Apache-2.0
"""FasterWhisper STT adapter implementing STTPort protocol."""

import struct
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from paaf_voice.engines.registry import register_stt_engine
from paaf_voice.ports import STT, AudioFrame, STTResult


@register_stt_engine("faster_whisper")
class FasterWhisperSTT(STT):
    """STT engine adapter wrapping faster-whisper (CTranslate2)."""

    def __init__(
        self,
        model_size_or_path: str = "base",
        device: str = "auto",
        compute_type: str = "default",
        download_root: str | None = None,
        language: str | None = None,
        model: Any = None,
    ) -> None:
        self.model_size_or_path = model_size_or_path
        self.device = device
        self.compute_type = compute_type
        self.download_root = download_root
        self.language = language
        self._model = model
        self._is_warmed_up = False

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as err:
            raise ImportError(
                "faster-whisper package is required for FasterWhisperSTT. "
                "Install it using `pip install faster-whisper`."
            ) from err

        self._model = WhisperModel(
            self.model_size_or_path,
            device=self.device,
            compute_type=self.compute_type,
            download_root=self.download_root,
        )
        return self._model

    def warmup(self) -> None:
        """Pre-load Whisper model weights into memory and run a dummy silence pass."""
        model = self._ensure_model()
        # 20ms of silence at 16kHz 16-bit mono = 320 samples = 640 bytes
        silence_bytes = b"\x00" * 640
        audio_data = _pcm16_to_audio(silence_bytes)
        try:
            model.transcribe(audio_data, language=self.language)
        except Exception:  # noqa: BLE001, S110
            pass
        self._is_warmed_up = True

    async def transcribe_stream(
        self, audio_stream: AsyncIterable[AudioFrame]
    ) -> AsyncIterator[STTResult]:
        """Transcribe an incoming stream of audio frames."""
        model = self._ensure_model()
        pcm_chunks = []

        async for frame in audio_stream:
            if frame.data:
                pcm_chunks.append(frame.data)

        if not pcm_chunks:
            return

        full_pcm = b"".join(pcm_chunks)
        if len(full_pcm) < 2:
            return

        audio_data = _pcm16_to_audio(full_pcm)
        result = model.transcribe(audio_data, language=self.language)

        if isinstance(result, tuple) and len(result) == 2:
            segments, info = result
        else:
            segments, info = result, None

        lang = getattr(info, "language", self.language)
        conf = float(getattr(info, "language_probability", 1.0)) if info else 1.0

        for segment in segments:
            text = getattr(segment, "text", str(segment)).strip()
            if text:
                yield STTResult(
                    text=text,
                    is_final=True,
                    language=lang,
                    confidence=conf,
                )


def _pcm16_to_audio(pcm_bytes: bytes) -> Any:
    """Convert PCM 16-bit mono bytes to normalized float audio array/list."""
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
