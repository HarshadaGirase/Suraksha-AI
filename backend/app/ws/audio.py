"""WS#1 — React mic <-> FastAPI (CLAUDE.MD §7, §9).

Binary frames are 16kHz PCM16 mono, downsampled client-side per §7.4. JSON
frames are the mode/scenario/act/vad control messages from §9. Everything the
client renders leaves through here as a §9 event.

Two pumps run concurrently: one draining the browser socket into AssemblyAI,
one draining the STT event queue back out. A third racer caps billed stream
time. Whichever finishes first tears down the others, so a dropped tab cannot
leak a live AssemblyAI stream -- which matters because §7 caps us at 5 streams
per minute.

Transcript events do not go straight to the browser: they pass through
CallSession, which routes them to the Guardian or the RescueAgent depending on
the act. Everything else is forwarded untouched.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.stt.aai import SttSession
from app.ws.events import (
    ConnectionStatus,
    ErrorEvent,
    Event,
    ThreatUpdate,
    parse_client_message,
)
from app.ws.session import CallSession

log = logging.getLogger(__name__)
router = APIRouter()


async def _pump_events(ws: WebSocket, stt: SttSession, call: CallSession) -> None:
    """STT events -> agents -> browser."""
    while True:
        event = await stt.events.get()
        kind = event.type

        # Transcripts are routed rather than forwarded: the agent needs to see
        # them, and CallSession emits the browser-facing event itself so the
        # speaker label is the one the current act implies.
        if kind == "transcript.partial":
            await call.on_partial(event.text, event.t)
        elif kind == "transcript.final":
            await call.on_final(event.text, event.t)
        else:
            await ws.send_json(event.dump())


async def _pump_audio(ws: WebSocket, stt: SttSession, call: CallSession) -> None:
    """Browser -> STT. Binary is audio; text is a §9 control message."""
    while True:
        message = await ws.receive()

        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000))

        if (pcm := message.get("bytes")) is not None:
            await stt.send(pcm)
            continue

        if (text := message.get("text")) is not None:
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                continue
            parsed = parse_client_message(raw)
            if parsed is None:
                log.debug("ignoring unknown client message: %s", raw.get("type"))
                continue
            await _handle_control(parsed, call)


async def _handle_control(parsed, call: CallSession) -> None:
    kind = parsed.type
    if kind == "act":
        await call.set_act(parsed.act)
    elif kind == "scenario":
        call.set_scenario(parsed.id)
    elif kind == "mode":
        call.set_mode(parsed.mode)
    elif kind == "vad":
        await call.on_vad(parsed.speaking)


@router.websocket("/ws/audio")
async def ws_audio(ws: WebSocket) -> None:
    await ws.accept()
    settings = get_settings()

    async def emit(event: Event) -> None:
        await ws.send_json(event.dump())

    # §16 BLANK-STATE POLICY: the UI starts idle and fills only from events,
    # so the opening frames say "standby", never a fabricated value.
    await ws.send_json(ConnectionStatus(service="stt", state="standby").dump())
    await ws.send_json(ThreatUpdate().dump())
    await ws.send_json(
        ConnectionStatus(
            service="gemini", state="online" if settings.has_gemini else "error"
        ).dump()
    )

    if not settings.has_stt:
        await ws.send_json(
            ErrorEvent(message="ASSEMBLYAI_API_KEY is not configured").dump()
        )
        await ws.send_json(ConnectionStatus(service="stt", state="error").dump())
        await ws.close()
        return

    # Credit guard: a key exists but streaming is switched off. Say so plainly
    # rather than opening a billed stream.
    if not settings.stt_enabled:
        await ws.send_json(
            ErrorEvent(
                message="Streaming is off (STT_ENABLED=false) — no AssemblyAI "
                        "credit will be spent. Set STT_ENABLED=true to test live."
            ).dump()
        )
        await ws.close()
        return

    call = CallSession(settings, emit)
    await call.set_act("rescue")

    stt = SttSession(settings, speaker="victim")
    try:
        await stt.start()
    except Exception as exc:
        log.exception("could not open AssemblyAI stream")
        await ws.send_json(ErrorEvent(message=f"STT connect failed: {exc}").dump())
        await ws.send_json(ConnectionStatus(service="stt", state="error").dump())
        await ws.close()
        return

    audio = asyncio.create_task(_pump_audio(ws, stt, call))
    events = asyncio.create_task(_pump_events(ws, stt, call))
    # Third racer: a hard ceiling on billed stream time. Without it, one tab
    # left open overnight quietly spends the whole credit balance.
    budget = asyncio.create_task(asyncio.sleep(settings.stt_max_session_seconds))
    tasks = (audio, events, budget)
    try:
        await asyncio.wait(set(tasks), return_when=asyncio.FIRST_COMPLETED)
        if budget.done():
            log.info("session budget reached (%ss)", settings.stt_max_session_seconds)
            await ws.send_json(
                ErrorEvent(
                    message=f"Session ended after "
                            f"{settings.stt_max_session_seconds}s to protect "
                            f"streaming credit. Reconnect to continue."
                ).dump()
            )
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await stt.stop()
        log.info("WS#1 closed")
