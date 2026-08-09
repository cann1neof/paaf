# SPDX-License-Identifier: Apache-2.0
import asyncio
from dataclasses import dataclass
from typing import Callable, Coroutine, Any, Dict, List
from paaf_voice.ports import AudioFrame
from paaf_session.arbitration import AudioPriority, AudioPriorityQueue

@dataclass
class EscalationTask:
    timeout: float
    priority: AudioPriority
    frame: AudioFrame

class BehaviorTable:
    def __init__(self):
        self._escalations: Dict[str, List[EscalationTask]] = {}
        
    def add_escalation(self, state: str, task: EscalationTask) -> None:
        if state not in self._escalations:
            self._escalations[state] = []
        self._escalations[state].append(task)
        
    async def _run_escalation(self, task: EscalationTask, queue: AudioPriorityQueue) -> None:
        try:
            await asyncio.sleep(task.timeout)
            queue.emit(task.priority, task.frame)
        except asyncio.CancelledError:
            pass

    async def run_with_escalations(self, state: str, coro_fn: Callable[[], Coroutine[Any, Any, Any]], queue: AudioPriorityQueue) -> Any:
        tasks_list = self._escalations.get(state, [])
        if not tasks_list:
            return await coro_fn()
            
        async def wrap():
            return await coro_fn()
            
        async with asyncio.TaskGroup() as tg:
            m_task = tg.create_task(wrap())
            e_tasks = [tg.create_task(self._run_escalation(t, queue)) for t in tasks_list]
            
            # Wait for main task to finish
            result = await m_task
            
            # Cancel all pending escalations
            for e in e_tasks:
                if not e.done():
                    e.cancel()
                    
            return result
