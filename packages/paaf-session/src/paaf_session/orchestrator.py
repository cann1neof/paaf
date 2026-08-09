# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
from enum import Enum, auto
from collections.abc import AsyncIterator, AsyncIterable
from typing import Callable

from paaf_voice.ports import AudioSource, AudioSink, STT, TTS, AudioFrame
from paaf_voice.aggregator import SentenceAggregator
from paaf_session.arbitration import AudioPriorityQueue, AudioPriority
from paaf_session.behaviors import BehaviorTable

logger = logging.getLogger(__name__)


class ModelUnavailableError(Exception):
    pass

class ToolError(Exception):
    pass

class BargeInInterrupt(Exception):
    pass

class TurnState(Enum):
    IDLE = auto()
    WAKE = auto()
    CAPTURE = auto()
    TRANSCRIBE = auto()
    THINK = auto()
    SPEAK = auto()

class TurnOrchestrator:
    def __init__(
        self,
        audio_source: AudioSource,
        audio_sink: AudioSink,
        stt: STT,
        tts: TTS,
        llm_generate: Callable[[str], AsyncIterator[str]],
    ):
        self.source = audio_source
        self.sink = audio_sink
        self.stt = stt
        self.tts = tts
        self.audio_queue = AudioPriorityQueue(audio_sink)
        self.behaviors = BehaviorTable()
        self.llm_generate = llm_generate
        self.follow_up_timeout = 5.0
        self.state = TurnState.IDLE
        self.committed_history: list[str] = []
        self._shutdown = asyncio.Event()
        self._loop_task: asyncio.Task | None = None
        self._wake_event = asyncio.Event()

    async def start(self) -> None:
        if self._loop_task is not None:
            return
        self._shutdown.clear()
        self._loop_task = asyncio.create_task(self._run_loop())
        await self.audio_queue.start()

    async def stop(self) -> None:
        if self._loop_task is None:
            return
        self._shutdown.set()
        self._wake_event.set()
        self._loop_task.cancel()
        await self.audio_queue.stop()
        try:
            await self._loop_task
        except asyncio.CancelledError:
            pass
        self._loop_task = None

    def trigger_wake(self) -> None:
        self._wake_event.set()

    async def _run_loop(self) -> None:
        while not self._shutdown.is_set():
            if self.state == TurnState.IDLE:
                await self._wake_event.wait()
                if self._shutdown.is_set():
                    break
                self._wake_event.clear()
            
            try:
                # Use TaskGroup for cancellation scopes (D-01)
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self.run_turn())
            except asyncio.CancelledError:
                pass
            finally:
                if not self._shutdown.is_set():
                    self.state = TurnState.IDLE

    async def run_turn(self, initial_timeout: float | None = None) -> None:
        """Run the end-to-end turn loop."""
        timeout = initial_timeout
        if self.state == TurnState.IDLE:
            self.state = TurnState.WAKE
        
        while self.state != TurnState.IDLE:
            if self.state == TurnState.WAKE:
                self.state = TurnState.CAPTURE

            elif self.state == TurnState.CAPTURE:
                self.state = TurnState.TRANSCRIBE
                # Capture and transcribe concurrently
                transcribed_text = await self._capture_and_transcribe(timeout)
                if not transcribed_text:
                    self.state = TurnState.IDLE
                else:
                    self._last_transcription = transcribed_text
                    self.state = TurnState.THINK

            elif self.state == TurnState.THINK:
                # We start LLM generation, but speech starts as soon as we have a sentence
                self.state = TurnState.SPEAK

            elif self.state == TurnState.SPEAK:
                monitor_task = None
                interrupt_detected = False
                try:
                    async with asyncio.TaskGroup() as tg:
                        monitor_task = tg.create_task(self._monitor_interrupt())
                        
                        async def speak_and_cancel():
                            async def do_think():
                                await self._think_and_speak(self._last_transcription)
                            await self.behaviors.run_with_escalations("THINK", do_think, self.audio_queue)
                            monitor_task.cancel()
                            
                        tg.create_task(speak_and_cancel())
                except* BargeInInterrupt:
                    interrupt_detected = True
                except* asyncio.CancelledError:
                    pass

                played = self.sink.get_played_chunks()
                self.committed_history.extend(played)

                if interrupt_detected:
                    self.state = TurnState.CAPTURE
                    timeout = None
                else:
                    # D-04: Transition back to CAPTURE after SPEAK with a follow-up timeout
                    self.state = TurnState.CAPTURE
                    timeout = self.follow_up_timeout

    async def _capture_and_transcribe(self, timeout: float | None) -> str:
        """Capture audio and run STT, respecting the timeout."""
        # Using a bounded queue if we want to separate capture from STT, 
        # or we can directly pass the source async iterable.
        
        async def do_transcribe():
            stream = self.source.read_frames()
            final_text = ""
            async for result in self.stt.transcribe_stream(stream):
                if result.is_final:
                    final_text += result.text
                    break
            return final_text

        # D-03: Execute timeouts via background asyncio tasks spawned at the start of the state that sleep and race the main task.
        transcribe_task = asyncio.create_task(do_transcribe())
        
        if timeout is not None:
            async def timeout_waiter():
                await asyncio.sleep(timeout)
                return None
            timeout_task = asyncio.create_task(timeout_waiter())
            done, pending = await asyncio.wait(
                [transcribe_task, timeout_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
            
            if transcribe_task in done:
                return transcribe_task.result()
            else:
                return ""  # Timeout occurred
        else:
            return await transcribe_task

    async def _think_and_speak(self, prompt: str) -> None:
        """Process LLM tokens, aggregate to sentences, and synthesize TTS."""
        aggregator = SentenceAggregator()
        token_stream = self.llm_generate(prompt)
        sentence_stream = aggregator.aggregate_stream(token_stream)
        
        async def sentence_generator():
            async for sentence in sentence_stream:
                if hasattr(self.sink, "mark_chunk"):
                    self.sink.mark_chunk(sentence)
                async for frame in self.tts.synthesize(sentence):
                    self.audio_queue.emit(AudioPriority.REPLY, frame)
                    
        await sentence_generator()

    async def _monitor_interrupt(self) -> None:
        """Monitor audio input during playback for interruptions."""
        stream = self.source.read_frames(frame_duration_ms=20)
        async for result in self.stt.transcribe_stream(stream):
            if result.text.strip():
                raise BargeInInterrupt()
