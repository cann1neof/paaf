import asyncio
import pytest
from unittest.mock import Mock
from paaf_session.behaviors import BehaviorTable, EscalationTask
from paaf_voice.ports import AudioFrame
from paaf_session.arbitration import AudioPriority

@pytest.mark.asyncio
async def test_timeout_escalation():
    """A long request correctly triggers timed escalations sequentially using asyncio.sleep."""
    table = BehaviorTable()
    frame_ambient = AudioFrame(data=b"ambient")
    frame_speech = AudioFrame(data=b"speech")
    
    table.add_escalation("THINK", EscalationTask(timeout=0.05, priority=AudioPriority.FILLER, frame=frame_ambient))
    table.add_escalation("THINK", EscalationTask(timeout=0.1, priority=AudioPriority.REPLY, frame=frame_speech))
    
    mock_queue = Mock()
    mock_queue.emit = Mock()
    
    # We will simulate the racing tasks directly or via a method on the table
    # The action says: "Spawn background asyncio.sleep tasks at the start of a long state that race the main task (per D-03)."
    # Let's write a runner that takes the main task and the state escalations
    async def main_task_slow():
        await asyncio.sleep(0.15)
        return "done"
        
    result = await table.run_with_escalations("THINK", main_task_slow(), mock_queue)
    assert result == "done"
    
    calls = mock_queue.emit.call_args_list
    assert len(calls) == 2
    # First escalation
    assert calls[0].args == (AudioPriority.FILLER, frame_ambient)
    # Second escalation
    assert calls[1].args == (AudioPriority.REPLY, frame_speech)
