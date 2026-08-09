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
        
    result = await table.run_with_escalations("THINK", main_task_slow, mock_queue)
    assert result == "done"
    
    calls = mock_queue.emit.call_args_list
    assert len(calls) == 2
    # First escalation
    assert calls[0].args == (AudioPriority.FILLER, frame_ambient)
    # Second escalation
    assert calls[1].args == (AudioPriority.REPLY, frame_speech)

from paaf_session.orchestrator import TurnOrchestrator, TurnState, ModelUnavailableError, ToolError

@pytest.mark.asyncio
async def test_error_wake_behaviors():
    """Model-unavailable or tool-error exceptions trigger specific behavior feedback."""
    mock_source = Mock()
    mock_sink = Mock()
    mock_stt = Mock()
    mock_tts = Mock()
    mock_llm = Mock()
    
    orchestrator = TurnOrchestrator(
        mock_source, mock_sink, mock_stt, mock_tts, mock_llm
    )
    
    frame_wake = AudioFrame(data=b"wake")
    frame_model_err = AudioFrame(data=b"model_error")
    frame_tool_err = AudioFrame(data=b"tool_error")
    
    orchestrator.behaviors.set_event_behavior("wake", frame_wake)
    orchestrator.behaviors.set_event_behavior("model_unavailable", frame_model_err)
    orchestrator.behaviors.set_event_behavior("tool_error", frame_tool_err)
    
    orchestrator.audio_queue = Mock()
    
    call_count = 0
    async def mock_capture_transcribe(*args, **kwargs):
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            raise ModelUnavailableError("model down")
        elif call_count == 1:
            call_count += 1
            raise ToolError("tool failed")
        return ""
        
    orchestrator._capture_and_transcribe = mock_capture_transcribe
    
    orchestrator.state = TurnState.WAKE
    await orchestrator.run_turn()
    assert orchestrator.state == TurnState.IDLE
    
    orchestrator.state = TurnState.WAKE
    await orchestrator.run_turn()
    assert orchestrator.state == TurnState.IDLE
    
    calls = orchestrator.audio_queue.emit.call_args_list
    assert len(calls) == 4
    assert calls[0].args == (AudioPriority.FILLER, frame_wake)
    assert calls[1].args == (AudioPriority.FILLER, frame_model_err)
    assert calls[2].args == (AudioPriority.FILLER, frame_wake)
    assert calls[3].args == (AudioPriority.FILLER, frame_tool_err)
