# SPDX-License-Identifier: Apache-2.0

import asyncio
import time
import pytest

from paaf_session.orchestrator import TurnOrchestrator, TurnState
from paaf_voice.testing.fakes import (
    FakeAudioSource,
    FakeAudioSink,
    FakeSTT,
    FakeTTS,
)
from paaf_voice.ports import STTResult

async def mock_llm_generate(prompt: str):
    tokens = ["This ", "is ", "the ", "first ", "sentence. ", "Here ", "is ", "another ", "one."]
    for t in tokens:
        yield t
        await asyncio.sleep(0.01)

class OneShotSTT(FakeSTT):
    async def transcribe_stream(self, audio_stream):
        async for _ in audio_stream:
            pass
        self.transcribed_stream_count += 1
        if self.transcribed_stream_count == 1:
            yield STTResult("Hello world", True)
        else:
            yield STTResult("", True)

@pytest.mark.asyncio
async def test_happy_path_turn_loop():
    source = FakeAudioSource(pcm_data=b"\x00" * 16000 * 2) # 1 sec of audio
    sink = FakeAudioSink(mode="instant")
    stt = OneShotSTT()
    tts = FakeTTS()
    
    orchestrator = TurnOrchestrator(
        audio_source=source,
        audio_sink=sink,
        stt=stt,
        tts=tts,
        llm_generate=mock_llm_generate
    )
    
    # run_turn directly for deterministic testing without background loop overhead
    await orchestrator.run_turn(initial_timeout=0.1)
    
    assert orchestrator.state == TurnState.IDLE
    assert len(tts.synthesized_texts) == 2
    assert "This is the first sentence." in tts.synthesized_texts[0]
    assert "Here is another one." in tts.synthesized_texts[1]
    assert len(sink.recorded_frames) > 0

@pytest.mark.asyncio
async def test_streaming_tts_starts_early():
    source = FakeAudioSource(pcm_data=b"\x00" * 16000 * 2)
    sink = FakeAudioSink(mode="instant")
    stt = OneShotSTT()
    
    first_sentence_time = 0
    full_response_time = 0

    class TrackingFakeTTS(FakeTTS):
        async def synthesize(self, text: str, voice_id: str | None = None):
            nonlocal first_sentence_time
            if not first_sentence_time:
                first_sentence_time = time.monotonic()
            async for frame in super().synthesize(text, voice_id):
                yield frame

    async def slow_mock_llm(prompt: str):
        nonlocal full_response_time
        tokens = ["This ", "is ", "the ", "first ", "sentence. ", "Here ", "is ", "another ", "one."]
        for t in tokens:
            yield t
            await asyncio.sleep(0.05) # slow down LLM
        full_response_time = time.monotonic()

    tts = TrackingFakeTTS()
    orchestrator = TurnOrchestrator(
        audio_source=source,
        audio_sink=sink,
        stt=stt,
        tts=tts,
        llm_generate=slow_mock_llm
    )
    
    await orchestrator.run_turn(initial_timeout=0.1)
    
    assert first_sentence_time > 0
    assert full_response_time > 0
    assert first_sentence_time < full_response_time, "TTS should begin processing before LLM finishes the full response."

@pytest.mark.asyncio
async def test_follow_up_window_timeout():
    source = FakeAudioSource(pcm_data=b"\x00" * 16000 * 2)
    sink = FakeAudioSink(mode="instant")
    
    stt = OneShotSTT()
    tts = FakeTTS()
    
    orchestrator = TurnOrchestrator(
        audio_source=source,
        audio_sink=sink,
        stt=stt,
        tts=tts,
        llm_generate=mock_llm_generate
    )
    
    orchestrator.follow_up_timeout = 0.1 

    await orchestrator.run_turn(initial_timeout=0.1)
    
    assert orchestrator.state == TurnState.IDLE
    assert stt.transcribed_stream_count == 3
