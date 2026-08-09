import asyncio
import time
import pytest
from paaf_session.orchestrator import TurnOrchestrator, TurnState
from paaf_voice.testing.fakes import FakeAudioSource, FakeAudioSink, FakeSTT, FakeTTS
from paaf_voice.ports import STTResult

class SlowFakeTTS(FakeTTS):
    async def synthesize(self, text: str, voice_id: str | None = None):
        # synthesize very slowly to allow interrupt to happen
        async for frame in super().synthesize(text, voice_id):
            yield frame
            await asyncio.sleep(0.1)

async def mock_llm_generate(prompt: str):
    tokens = ["This ", "is ", "a ", "long ", "sentence. "]
    for t in tokens:
        yield t
        await asyncio.sleep(0.01)

class InterruptSTT(FakeSTT):
    def __init__(self):
        super().__init__()
        self.call_count = 0
        
    async def transcribe_stream(self, audio_stream):
        self.call_count += 1
        if self.call_count == 1:
            count = 0
            async for frame in audio_stream:
                count += 1
                if count > 5:
                    yield STTResult("What time is it?", True)
                    break
        else:
            async for frame in audio_stream:
                if b"\x01" in frame.data:
                    yield STTResult("Interrupt", True)
                    break

@pytest.mark.asyncio
async def test_barge_in_cancellation():
    # Simulate an interrupt by providing audio data that will be transcribed during SPEAK
    # 0.1 seconds of silence, then some audio that will trigger STT
    silence = b"\x00" * int(16000 * 2 * 0.1)  # 100 ms
    interrupt_audio = b"\x01" * int(16000 * 2 * 0.1) # 100 ms
    source = FakeAudioSource(pcm_data=silence + interrupt_audio, realtime=True)
    
    sink = FakeAudioSink(mode="1x")
    stt = InterruptSTT()
    tts = SlowFakeTTS()
    
    orchestrator = TurnOrchestrator(
        audio_source=source,
        audio_sink=sink,
        stt=stt,
        tts=tts,
        llm_generate=mock_llm_generate
    )
    
    # We need to run the full loop to test TaskGroup cancellation
    # So we'll trigger wake and wait for state changes
    asyncio.create_task(orchestrator.start())
    
    orchestrator.trigger_wake()
    
    try:
        # Wait until it reaches SPEAK state
        start_time = time.monotonic()
        while orchestrator.state != TurnState.SPEAK:
            await asyncio.sleep(0.01)
            if time.monotonic() - start_time > 2.0:
                pytest.fail("Did not reach SPEAK state in time")
                
        # Once in SPEAK state, it should be interrupted and go back to CAPTURE -> TRANSCRIBE
        interrupt_time = time.monotonic()
        while orchestrator.state != TurnState.TRANSCRIBE:
            await asyncio.sleep(0.01)
            if time.monotonic() - interrupt_time > 4.0:
                pytest.fail(f"Did not return to TRANSCRIBE after interrupt, state is {orchestrator.state}")
                
        latency = time.monotonic() - interrupt_time
        assert latency < 0.250, f"Barge-in latency was {latency}, expected < 0.250s"
    finally:
        await orchestrator.stop()
