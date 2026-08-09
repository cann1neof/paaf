import asyncio
import pytest
from unittest.mock import Mock
from paaf_session.arbitration import AudioPriorityQueue, AudioPriority
from paaf_voice.ports import AudioFrame

@pytest.mark.asyncio
async def test_audio_priority_arbitration():
    """A ready reply sentence preempts a filler behavior mid-word; they never play concurrently."""
    mock_sink = Mock()
    queue = AudioPriorityQueue(mock_sink)
    
    # We will enqueue items before starting so we can verify priority ordering
    frame_filler1 = AudioFrame(data=b"filler1")
    frame_filler2 = AudioFrame(data=b"filler2")
    frame_reply = AudioFrame(data=b"reply")
    
    # Queue filler then reply
    queue.emit(AudioPriority.FILLER, frame_filler1)
    queue.emit(AudioPriority.REPLY, frame_reply)
    queue.emit(AudioPriority.FILLER, frame_filler2)
    
    await queue.start()
    
    # Give the task time to process all items
    await asyncio.sleep(0.05)
    await queue.stop()
    
    calls = mock_sink.write_frame.call_args_list
    assert len(calls) == 3
    
    # The reply should preempt the fillers since it has higher priority
    # So the order of data written should be reply, then the fillers
    written_data = [call.args[0].data for call in calls]
    assert written_data == [b"reply", b"filler1", b"filler2"]

def test_emit_is_not_a_coroutine() -> None:
    """emit must be a plain sync method — it can never await on the hot path."""
    assert asyncio.iscoroutinefunction(AudioPriorityQueue.emit) is False
