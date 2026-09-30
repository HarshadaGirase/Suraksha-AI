"""GET /api/tts (CLAUDE.MD §7).

Plain HTTP, not a WebSocket. §7 allows exactly two sockets and this is not one
of them: the client gets a URL in a tts.play event and hands it straight to an
<audio> element, which also gives us browser-side caching for free.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Response

from app.config import get_settings
from app.tts.service import TtsUnavailable, synthesize

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/tts")
async def tts(
    text: str = Query(..., max_length=600),
    voice: str | None = Query(None),
) -> Response:
    """Synthesise one line.

    max_length is a guard, not a limit on speech: the agent's lines are one or
    two sentences, and an unbounded query string is an easy way to make an
    unauthenticated upstream service rate-limit us.
    """
    settings = get_settings()
    chosen = voice or settings.tts_voice_agent

    try:
        audio = await synthesize(text, chosen)
    except TtsUnavailable as exc:
        # 503, not 500: the client should keep showing the agent's text and
        # carry on. Losing the voice must never lose the conversation.
        raise HTTPException(status_code=503, detail=f"tts unavailable: {exc}") from exc

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
