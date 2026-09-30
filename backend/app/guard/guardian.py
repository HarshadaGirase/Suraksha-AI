"""Act 1 Guardian orchestrator (CLAUDE.MD §4, §7.1).

Watches the caller's transcript, arms when the threat is confirmed, and tells
the client to sever the victim's outbound channel.

The ordering is the whole design. Arming happens during the CALLER's turn,
where being slow is free -- the caller is still talking and nothing the victim
says has left the machine yet. The cut itself then happens client-side on local
VAD, with no network round trip, the instant the victim opens their mouth.

Gate 0 measured 1042-1125ms from first audio chunk to first partial. Any design
that waits for a transcript before muting has already lost by a full second;
per-word muting is not merely hard, it is impossible.
"""

import logging
import time
from typing import Awaitable, Callable

from app.guard.rules import Signal, contains_digits, evaluate, score, state_for
from app.ws.events import (
    Event,
    EvidenceUpdate,
    GuardAction,
    EvidenceSignal,
    StatUpdate,
    ThreatUpdate,
    TtsPlay,
)

log = logging.getLogger(__name__)

Emit = Callable[[Event], Awaitable[None]] | Callable[[Event], None]

# §13 Guardian. The counter-interrogation leads with the caller-number question
# because it is the one a scammer cannot talk his way out of: an employee ID
# can be invented on the spot, a 1600xx line cannot.
COUNTER_INTERROGATE = (
    "आप किस number से call कर रहे हैं? RBI के rules से bank सिर्फ 1600xx "
    "series से call करता है। अपना employee ID और branch code बताइए।"
)

TERMINATE_WARNING = (
    "यह call fraud है। मैंने call काट दी है। आपने कोई OTP नहीं दिया — "
    "आपका पैसा safe है।"
)


class Guardian:
    """One intercepted call."""

    def __init__(self, emit: Emit, *, caller_number: str | None = None) -> None:
        self._emit = emit
        self.caller_number = caller_number
        self._transcript: list[str] = []
        self._signals: dict[str, Signal] = {}
        self._armed = False
        self._cut = False
        self._interrogated = False
        self._armed_at: float | None = None
        self._digits_leaked = False

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def cut(self) -> bool:
        return self._cut

    async def on_caller_final(self, text: str) -> None:
        """A completed caller turn. Re-scores and arms if warranted."""
        if not text.strip():
            return
        self._transcript.append(text)
        await self._rescore()

    async def on_caller_partial(self, text: str) -> None:
        """Partials are scored too.

        Arming a turn earlier is free accuracy: the victim has not spoken yet,
        so there is nothing to lose by deciding while the caller is mid-sentence.
        """
        if not text.strip():
            return
        await self._rescore(pending=text)

    async def _rescore(self, *, pending: str = "") -> None:
        whole = " ".join([*self._transcript, pending])
        found = evaluate(whole, caller_number=self.caller_number)

        new = [s for s in found if s.name not in self._signals]
        for s in found:
            self._signals[s.name] = s

        total = score(list(self._signals.values()))
        state = state_for(total)
        await self._send(ThreatUpdate(score=total, state=state))

        if new:
            await self._send(
                EvidenceUpdate(
                    signals=[
                        EvidenceSignal(name=s.name, desc=s.desc, confidence=s.confidence)
                        for s in self._signals.values()
                    ]
                )
            )

        if state == "critical" and not self._armed:
            await self._arm()

    async def _arm(self) -> None:
        """Prime the channel cut. Does NOT mute yet.

        Muting here would cut the victim off mid-sentence during the caller's
        turn, which is both useless and confusing. The client holds the trigger
        and fires it on local VAD.
        """
        self._armed = True
        self._armed_at = time.monotonic()
        log.info("guard armed")
        await self._send(GuardAction(action="guard_rules", ms=0))

    async def on_victim_speaking(self) -> None:
        """Client reports local VAD while armed. The channel is now severed.

        The client has already muted by the time this arrives -- it does not
        wait for us, which is the entire point. This records that it happened
        and measures the loop.
        """
        if not self._armed or self._cut:
            return
        self._cut = True
        ms = int((time.monotonic() - (self._armed_at or time.monotonic())) * 1000)
        log.info("channel cut %dms after arming", ms)
        await self._send(GuardAction(action="channel_cut", ms=ms))
        await self._send(StatUpdate(key="guard_loop", value=f"{ms}ms"))
        # §17 redaction: the cut was in place before the victim's first
        # syllable left the machine. That is the whole claim, and it is
        # measurable. What they went on to SAY is not -- see on_victim_final.
        await self._send(StatUpdate(key="redaction", value="100%"))

        if not self._interrogated:
            self._interrogated = True
            await self._send(GuardAction(action="counter_interrogate", ms=0))
            await self._send(TtsPlay(url=f"/api/tts?text={COUNTER_INTERROGATE}"))

    async def on_victim_final(self, text: str) -> None:
        """A victim turn that reached STT despite the guard.

        This only fires when the cut did NOT happen -- if it had, the audio
        never left the machine and there would be no transcript to inspect.
        So digits arriving here are a guard FAILURE, recorded as such. Claiming
        "we saw the OTP and blocked it" would be claiming evidence the design
        guarantees we cannot have.
        """
        if not contains_digits(text):
            return
        self._digits_leaked = True
        log.warning("digits reached STT — channel was not cut in time")
        await self._send(StatUpdate(key="redaction", value="0%"))

    async def terminate(self) -> None:
        await self._send(GuardAction(action="terminate_call", ms=0))
        await self._send(TtsPlay(url=f"/api/tts?text={TERMINATE_WARNING}"))
        await self._send(GuardAction(action="warning_tts", ms=0))

    def forensic_record(self, case_id: str | None = None) -> dict:
        """The Act 1 document (§3).

        Reports what happened, including the awkward parts: if the guard never
        armed, this says so rather than claiming a save.
        """
        return {
            "case_id": case_id,
            "act": "intercept",
            "caller_number": self.caller_number,
            "caller_series_legal": (
                None if not self.caller_number
                else self.caller_number.lstrip("+").startswith("1600")
            ),
            "threat_score": score(list(self._signals.values())),
            "threat_state": state_for(score(list(self._signals.values()))),
            "signals": [
                {"name": s.name, "desc": s.desc, "confidence": s.confidence}
                for s in self._signals.values()
            ],
            "armed": self._armed,
            "channel_cut": self._cut,
            # What we can prove: the outbound channel was severed before the
            # victim's first syllable. What we deliberately CANNOT prove: what
            # they went on to say — if the cut worked, that audio never reached
            # STT. A claim of "we caught the OTP" would be evidence the design
            # guarantees we do not have.
            "victim_speech_blocked": self._cut,
            "digits_leaked_to_stt": self._digits_leaked,
            "amount_lost": 0 if self._cut and not self._digits_leaked else None,
            "transcript": self._transcript,
        }

    async def _send(self, event: Event) -> None:
        result = self._emit(event)
        if hasattr(result, "__await__"):
            await result
