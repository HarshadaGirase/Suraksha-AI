"""AssemblyAI streaming session — WS#2 (CLAUDE.MD §7).

The SDK ships two clients with identical surfaces: RealTimeTranscriber
(threaded) and AsyncRealTimeTranscriber (asyncio). We use the async one so
FastAPI's event loop is never blocked by stream() and so SDK callbacks don't
need run_coroutine_threadsafe bridging. (StreamingClient is just an alias for
the threaded class — verified by introspection, not docs.)

Events are translated into §9 contract messages and pushed onto a queue that
the WS#1 handler drains. Keeping translation here means the socket layer never
touches an AssemblyAI type.
"""

import asyncio
import logging
import time
from typing import Literal

from assemblyai.streaming.v3 import (
    AsyncRealTimeTranscriber,
    BeginEvent,
    Encoding,
    RealTimeError,
    RealTimeEvents,
    RealTimeParameters,
    RealTimeSessionParameters,
    RealTimeTranscriberOptions,
    TerminationEvent,
    TurnEvent,
)

from app.config import Settings
from app.ws.events import (
    ConnectionStatus,
    ErrorEvent,
    Event,
    StatUpdate,
    TranscriptFinal,
    TranscriptPartial,
    WordTs,
)

log = logging.getLogger(__name__)

Speaker = Literal["scammer", "victim", "agent"]

# §7.3 / API spec: chunks must be 50-1000ms. 100ms at 16kHz PCM16 = 3200 bytes.
CHUNK_MS = 100


class SttSession:
    """One AssemblyAI streaming connection, feeding §9 events onto a queue."""

    def __init__(self, settings: Settings, speaker: Speaker = "victim") -> None:
        self._settings = settings
        self._speaker = speaker
        self.events: asyncio.Queue[Event] = asyncio.Queue()
        self._client: AsyncRealTimeTranscriber | None = None
        self._first_chunk_at: float | None = None
        self._latency_reported = False
        self._started_at = time.monotonic()

    # ---------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        s = self._settings
        client = AsyncRealTimeTranscriber(
            RealTimeTranscriberOptions(terminate_timeout=10.0),
            api_key=s.assemblyai_api_key,
        )
        client.on(RealTimeEvents.Begin, self._on_begin)
        client.on(RealTimeEvents.Turn, self._on_turn)
        client.on(RealTimeEvents.Termination, self._on_termination)
        client.on(RealTimeEvents.Error, self._on_error)

        # universal-3-6-pro is the current flagship: 32 languages with native
        # code-switching, and it adds Marathi and Urdu over 3.5 Pro at no cost
        # to us. language_codes=["en","hi"] plus language_detection is the
        # documented way to steer code-switched audio. The singular
        # language_code is for monolingual sessions and would break Hinglish —
        # deliberately unset.
        await client.connect(
            RealTimeParameters(
                speech_model="universal-3-6-pro",
                encoding=Encoding.pcm_s16le,
                sample_rate=s.sample_rate,
                language_codes=["en", "hi"],
                language_detection=True,
                format_turns=True,
                include_partial_turns=True,
            )
        )
        self._client = client

    async def send(self, pcm: bytes) -> None:
        if self._client is None:
            return
        if self._first_chunk_at is None:
            self._first_chunk_at = time.monotonic()
        await self._client.stream(pcm)

    async def update_keyterms(self, terms: list[str]) -> None:
        """Arm or disarm guard vocabulary mid-session.

        The API allows up to 100 terms of <=50 chars, updatable with no
        reconnect — which matters because §7 warns that rapid reconnects hit
        the 5-streams-per-minute limit.
        """
        if self._client is None:
            return
        await self._client.set_params(
            RealTimeSessionParameters(keyterms_prompt=terms[:100])
        )

    async def stop(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.disconnect(terminate=True)
        except Exception as exc:  # a dying socket must not take down WS#1
            log.warning("STT disconnect failed: %s", exc)
        finally:
            self._client = None

    # ---------------------------------------------------------------- handlers

    def _emit(self, event: Event) -> None:
        self.events.put_nowait(event)

    def _on_begin(self, _client, event: BeginEvent) -> None:
        log.info("AssemblyAI session %s", event.id)
        self._emit(ConnectionStatus(service="stt", state="online"))

    def _on_turn(self, _client, event: TurnEvent) -> None:
        if not event.transcript:
            return

        # §17: stt_latency = first chunk -> first partial. Measured, never guessed.
        if not self._latency_reported and self._first_chunk_at is not None:
            ms = (time.monotonic() - self._first_chunk_at) * 1000
            self._emit(StatUpdate(key="stt_latency", value=f"{ms:.0f}ms"))
            self._latency_reported = True

        t = round(time.monotonic() - self._started_at, 2)
        cls = TranscriptFinal if event.end_of_turn else TranscriptPartial
        self._emit(cls(speaker=self._speaker, text=event.transcript, t=t))

        # Word timings drive the ••••••  rendering and the forensic record.
        # PLAN.md C1: display and evidence only — never the mute trigger.
        for w in event.words or []:
            if w.word_is_final:
                self._emit(WordTs(word=w.text, start=w.start / 1000, end=w.end / 1000))

    def _on_termination(self, _client, event: TerminationEvent) -> None:
        log.info("AssemblyAI terminated after %ss", event.audio_duration_seconds)
        self._emit(ConnectionStatus(service="stt", state="standby"))

    def _on_error(self, _client, error: RealTimeError) -> None:
        log.error("AssemblyAI error: %s", error)
        self._emit(ConnectionStatus(service="stt", state="error"))
        self._emit(ErrorEvent(message=str(error)))
