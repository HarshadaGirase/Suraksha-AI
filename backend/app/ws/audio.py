"""WS#1 — React mic <-> FastAPI (CLAUDE.MD §7).

Binary frames are 16kHz PCM16 mono, downsampled client-side per §7.3. JSON
frames are the mode/scenario/act control messages from §9. Everything the
client renders leaves through here as a §9 event.

Two pumps run concurrently: one draining the browser socket into AssemblyAI,
one draining the STT event queue back out to the browser. Either ending tears
down the other, so a dropped tab cannot leak a live AssemblyAI stream — which
matters because §7 caps us at 5 streams per minute.
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
    ThreatUpdate,
    parse_client_message,
)

log = logging.getLogger(__name__)
router = APIRouter()


async def _pump_events(ws: WebSocket, session: SttSession) -> None:
    """STT events -> browser."""
    while True:
        event = await session.events.get()
        await ws.send_json(event.dump())


async def _pump_audio(ws: WebSocket, session: SttSession) -> None:
    """Browser -> STT. Binary is audio; text is a §9 control message."""
    while True:
        message = await ws.receive()

        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000))

        if (pcm := message.get("bytes")) is not None:
            await session.send(pcm)
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
            log.info("control: %s", parsed.model_dump())


@router.websocket("/ws/audio")
async def ws_audio(ws: WebSocket) -> None:
    await ws.accept()
    settings = get_settings()

    # §16 BLANK-STATE POLICY: the UI starts idle and fills only from events,
    # so the opening frames say "standby", never a fabricated value.
    await ws.send_json(ConnectionStatus(service="stt", state="standby").dump())
    await ws.send_json(ThreatUpdate().dump())

    if not settings.has_stt:
        await ws.send_json(
            ErrorEvent(message="ASSEMBLYAI_API_KEY is not configured").dump()
        )
        await ws.send_json(ConnectionStatus(service="stt", state="error").dump())
        await ws.close()
        return

    # Credit guard: a key exists but streaming is switched off. Say so plainly
    # rather than opening a billed stream, and stay connected so the UI reads
    # as idle-by-choice instead of broken.
    if not settings.stt_enabled:
        await ws.send_json(
            ErrorEvent(
                message="Streaming is off (STT_ENABLED=false) — no AssemblyAI "
                        "credit will be spent. Set STT_ENABLED=true to test live."
            ).dump()
        )
        await ws.close()
        return

    session = SttSession(settings, speaker="victim")
    try:
        await session.start()
    except Exception as exc:
        log.exception("could not open AssemblyAI stream")
        await ws.send_json(ErrorEvent(message=f"STT connect failed: {exc}").dump())
        await ws.send_json(ConnectionStatus(service="stt", state="error").dump())
        await ws.close()
        return

    audio = asyncio.create_task(_pump_audio(ws, session))
    events = asyncio.create_task(_pump_events(ws, session))
    # Third racer: a hard ceiling on billed stream time. Without it, one tab
    # left open overnight quietly spends the whole credit balance.
    budget = asyncio.create_task(asyncio.sleep(settings.stt_max_session_seconds))
    tasks = (audio, events, budget)
    try:
        # Whichever finishes first ends the call; the others are cancelled below.
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
        await session.stop()
        log.info("WS#1 closed")
