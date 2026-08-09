# SPDX-License-Identifier: Apache-2.0
"""WhisperCpp STT adapter implementing STTPort protocol."""

import struct
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from paaf_voice.engines.registry import register_stt_engine
from paaf_voice.ports import STT, AudioFrame, STTResult


@register_stt_engine("whisper_cpp")
class WhisperCppSTT(STT):
    """STT engine adapter wrapping whisper.cpp / pywhispercpp for ARM/low-resource devices."""

    def __init__(
        self,
        model_path: str = "ggml-base.bin",
        n_threads: int = 4,
        language: str | None = None,
        model: Any = None,
    ) -> None:
        self.model_path = model_path
        self.n_threads = n_threads
        self.language = language
        self._model = model
        self._is_warmed_up = False

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from pywhispercpp.model import Model
        except ImportError as err:
            raise ImportError(
                "pywhispercpp package is required for WhisperCppSTT. "
                "Install it using `pip install pywhispercpp`."
            ) from err

        self._model = Model(
            self.model_path,
            n_threads=self.n_threads,
        )
        return self._model

    def warmup(self) -> None:
        """Pre-load whisper.cpp GGML model into memory and run dummy silence pass."""
        model = self._ensure_model()
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
        res = model.transcribe(audio_data, language=self.language)

        if isinstance(res, tuple) and len(res) == 2:
            segments, info = res
        else:
            segments, info = res, None

        lang = getattr(info, "language", self.language) if info else self.language
        conf = float(getattr(info, "language_probability", 1.0)) if info else 1.0

        if isinstance(segments, list | tuple):
            for segment in segments:
                text = getattr(segment, "text", str(segment)).strip()
                seg_lang = getattr(segment, "language", lang)
                if text:
                    yield STTResult(
                        text=text,
                        is_final=True,
                        language=seg_lang,
                        confidence=conf,
                    )
        elif segments:
            text = getattr(segments, "text", str(segments)).strip()
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
