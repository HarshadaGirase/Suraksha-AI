"""Act 2 rescue orchestrator (CLAUDE.MD §4, §10, §13).

Drives the four tools off the victim's speech while they are still talking.
The agent is not asked to be disciplined about ordering -- it is given the
tools and the order emerges, but this module owns the side effects and refuses
anything out of sequence.

Two guardrails run before any tool, on every single turn:

  1. OTP offered      -> interrupt, refuse, do not persist the turn verbatim.
  2. Digit run >= 4   -> redacted before it reaches the database.

The first is the one that matters. An AI that accepts an OTP is
indistinguishable from the scam it exists to fight, and a long emotional
code-switched conversation is exactly where a system prompt gets forgotten. So
it is enforced here in code, not only in the prompt.
"""

import logging
import time
from typing import Awaitable, Callable

from app.agents.clock import RescueClock
from app.agents.gemini import GeminiAgent, GeminiUnavailable, ToolCall
from app.agents.prompts import RESCUE_AGENT
from app.config import Settings
from app.db import cases as repo
from app.redact import contains_digit_run, redact_digits
from app.tools.rescue_tools import EXECUTORS, RescueState
from app.tools.schemas import RESCUE_TOOLS
from app.ws.events import (
    CaseUpdate,
    DocReady,
    ErrorEvent,
    Event,
    StatUpdate,
    ToolCall as ToolCallEvent,
    ToolResult,
    TranscriptFinal,
    TtsPlay,
)

log = logging.getLogger(__name__)

Emit = Callable[[Event], Awaitable[None]] | Callable[[Event], None]

# §13. Spoken verbatim, never paraphrased by the model — this line is the
# product's single most important sentence and it must not drift.
OTP_REFUSAL = "वो OTP मुझे मत बताइए! सब आप खुद portal पे डालेंगी।"

# §14 hero line 1, played from cache so the opener has zero latency.
OPENER = "मैं सुन रही हूँ — आप safe हैं। आराम से बताइए क्या हुआ?"

CLOSING = "Documents ready हैं — download कर लीजिए और 1930 पे file कर दीजिए।"

# Words that mean "the victim is about to read out a credential". Kept
# deliberately broad: a false positive costs one extra reassurance, a false
# negative puts an OTP in the database.
_OTP_CUES = (
    "otp", "ओटीपी", "pin", "पिन", "password", "पासवर्ड", "cvv",
    "one time", "one-time", "passcode", "code hai", "कोड है",
)


class RescueAgent:
    """One rescue conversation."""

    def __init__(self, settings: Settings, emit: Emit) -> None:
        self._settings = settings
        self._emit = emit
        self._state = RescueState()
        self._agent = GeminiAgent(
            settings, system_prompt=RESCUE_AGENT, tools=RESCUE_TOOLS
        )
        self._first_final_at: float | None = None
        self._opened = False

    @property
    def state(self) -> RescueState:
        return self._state

    @property
    def clock(self) -> RescueClock:
        return self._state.clock

    async def open(self) -> None:
        """Play the cached opener. No model call — latency here is what makes
        the difference between 'someone is listening' and 'a form loaded'."""
        if self._opened:
            return
        self._opened = True
        await self._send(TtsPlay(url=f"/api/tts?text={OPENER}"))

    async def on_victim_final(self, text: str) -> None:
        """One completed victim turn."""
        if not text.strip():
            return

        if self._first_final_at is None:
            self._first_final_at = time.monotonic()

        # Guardrail 1. Runs before the model sees the turn, so a victim
        # mid-OTP is interrupted rather than transcribed into a tool argument.
        if _offers_credential(text):
            await self._refuse_credential(text)
            return

        # Guardrail 2. The guard path may see raw text; the record may not.
        self._state.transcript.append(
            {"speaker": "victim", "text": redact_digits(text)}
        )

        try:
            reply, calls = await self._agent.turn(text, force_tool=not self._state.case_id)
        except GeminiUnavailable as exc:
            log.warning("gemini unavailable: %s", exc)
            await self._send(ErrorEvent(message=f"Agent unavailable: {exc}"))
            return

        await self._run_tools(calls)

        # Prefer our own question over the model's phrasing: the ask order is
        # chosen for what CFCFRMS actually needs, not for conversational flow.
        question = self._state.next_question() if self._state.case_id else None
        if question is not None:
            _, phrase = question
            await self._speak(phrase)
        elif reply:
            await self._speak(reply)

        if self._state.ready_to_draft() and self._state.draft is None:
            await self._draft()

    async def _run_tools(self, calls: list[ToolCall]) -> None:
        for call in calls:
            executor = EXECUTORS.get(call.name)
            if executor is None:
                log.warning("unknown tool %s", call.name)
                continue

            await self._send(ToolCallEvent(name=call.name, args=call.args))
            started = time.monotonic()
            try:
                result = await executor(self._state, call.args)
            except Exception as exc:
                log.exception("tool %s failed", call.name)
                result = {"error": str(exc)}
            ms = int((time.monotonic() - started) * 1000)

            await self._send(ToolResult(name=call.name, ms=ms, result=result))
            await repo.log_tool_event(
                case_id=self._state.case_id, name=call.name,
                args=call.args, result=result, ms=ms,
            )

            if call.name == "create_case" and self._state.case_id:
                await self._send_case_update()
            elif call.name == "extract_entities" and self._state.case_id:
                await self._send_case_update()

    async def _draft(self) -> None:
        """Produce the complaint draft.

        Asked for explicitly rather than waited for: the model will happily
        keep making sympathetic conversation forever, and the victim needs the
        document.
        """
        s = self._state
        summary = (
            f"Case {s.case_id} is open: {s.fraud_type}, ₹{s.amount}, "
            f"app={s.app}, UTR={s.utr}, when={s.when_ago}. "
            "Call draft_1930_report now with the Hindi victim statement, "
            "built only from what the victim actually said."
        )
        try:
            _, calls = await self._agent.turn(summary, force_tool=True)
        except GeminiUnavailable as exc:
            await self._send(ErrorEvent(message=f"Draft unavailable: {exc}"))
            return

        await self._run_tools([c for c in calls if c.name == "draft_1930_report"])

        if self._state.draft is None:
            return

        elapsed = self._state.clock.elapsed()
        await self._send(
            DocReady(doc="1930", download_url=f"/api/case/{self._state.case_id}/docs")
        )
        # §17 rescue_loop = first victim final -> draft ready. Measured.
        if self._first_final_at is not None:
            await self._send(
                StatUpdate(
                    key="rescue_loop",
                    value=f"{time.monotonic() - self._first_final_at:.1f}s",
                )
            )
        log.info("case %s drafted in %.1fs", self._state.case_id, elapsed)
        await self._speak(CLOSING)

    async def _refuse_credential(self, text: str) -> None:
        """Interrupt, and keep the masked turn as evidence the guard fired."""
        log.info("credential offered — refusing")
        masked = redact_digits(text)
        self._state.transcript.append(
            {"speaker": "victim", "text": masked, "guard": "credential_refused"}
        )
        await self._send(TranscriptFinal(speaker="victim", text=masked, t=0.0))
        await self._speak(OTP_REFUSAL)
        if self._state.case_id:
            await repo.log_tool_event(
                case_id=self._state.case_id,
                name="guard_credential_refused",
                args={}, result={"masked": True},
            )

    async def _speak(self, text: str) -> None:
        await self._send(TranscriptFinal(speaker="agent", text=text, t=0.0))
        await self._send(TtsPlay(url=f"/api/tts?text={text}"))

    async def _send_case_update(self) -> None:
        s = self._state
        await self._send(
            CaseUpdate(
                case_id=s.case_id or "",
                fraud_type=s.fraud_type,
                confidence=s.confidence,
                amount=s.amount,
                app=s.app,
                when_ago=s.when_ago,
                district=s.district,
            )
        )

    async def _send(self, event: Event) -> None:
        result = self._emit(event)
        if hasattr(result, "__await__"):
            await result


def _offers_credential(text: str) -> bool:
    """True when the victim looks about to read out a code.

    Requires a cue word AND a digit run. Either alone is common and harmless:
    "OTP aaya tha" is narration, "40000" is the amount. Together they are the
    thing we must never let through.
    """
    lowered = text.lower()
    if not any(cue in lowered for cue in _OTP_CUES):
        return False
    return contains_digit_run(text)
