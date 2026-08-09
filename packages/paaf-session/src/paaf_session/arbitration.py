# SPDX-License-Identifier: Apache-2.0
import asyncio
from enum import IntEnum
from paaf_voice.ports import AudioSink, AudioFrame

class AudioPriority(IntEnum):
    REPLY = 0   # Lower number = higher priority
    FILLER = 1

class AudioPriorityQueue:
    """Non-blocking async queue pattern for audio arbitration."""
    def __init__(self, sink: AudioSink):
        self.sink = sink
        self._q: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._writer_task: asyncio.Task | None = None
        self._order_counter = 0

    def emit(self, priority: AudioPriority, frame: AudioFrame) -> None:
        """Hand an event to the writer WITHOUT blocking (hot-path safe)."""
        # We use _order_counter to maintain FIFO for same-priority items
        self._order_counter += 1
        self._q.put_nowait((priority.value, self._order_counter, frame))

    async def start(self) -> None:
        if self._writer_task is not None:
            return
        self._writer_task = asyncio.create_task(self._writer())

    async def stop(self) -> None:
        if self._writer_task is None:
            return
        self._writer_task.cancel()
        try:
            await self._writer_task
        except asyncio.CancelledError:
            pass
        self._writer_task = None

    async def _writer(self) -> None:
        while True:
            _, _, frame = await self._q.get()
            try:
                self.sink.write_frame(frame)
            finally:
                self._q.task_done()
