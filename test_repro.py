import asyncio
from unittest.mock import Mock
from paaf_session.behaviors import BehaviorTable, EscalationTask
from paaf_voice.ports import AudioFrame
from paaf_session.arbitration import AudioPriority

async def test_timeout_escalation():
    table = BehaviorTable()
    frame_ambient = AudioFrame(data=b"ambient")
    table.add_escalation("THINK", EscalationTask(timeout=0.05, priority=AudioPriority.FILLER, frame=frame_ambient))
    mock_queue = Mock()
    
    async def main_task_slow():
        await asyncio.sleep(0.15)
        return "done"
        
    try:
        async with asyncio.TaskGroup() as tg:
            m_task = tg.create_task(main_task_slow())
            e_task = tg.create_task(table._run_escalation(EscalationTask(0.05, AudioPriority.FILLER, frame_ambient), mock_queue))
            await m_task
            e_task.cancel()
    except BaseException as e:
        print(repr(e))
        import traceback
        traceback.print_exc()

asyncio.run(test_timeout_escalation())
