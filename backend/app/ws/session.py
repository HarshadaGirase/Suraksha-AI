"""Per-connection session state (CLAUDE.MD §4, §9).

One WS#1 connection is one call, and a call is in exactly one act:

  intercept (Act 1) -- the caller is a scammer, the Guardian watches and arms
  rescue    (Act 2) -- the caller is a victim, the RescueAgent builds the case

The act is chosen by the client's {"type":"act"} message and decides who the
speaker label belongs to, which agent sees the transcript, and whether the
channel cut is armed at all.

Act 2 is the default. A person who opens the page without choosing is far more
likely to be someone who has already lost money than someone with a scammer
live on the line.
"""

import logging
from typing import Awaitable, Callable

from app.agents.rescue import RescueAgent
from app.config import Settings
from app.guard.guardian import Guardian
from app.ws.events import Event, TranscriptFinal, TranscriptPartial

log = logging.getLogger(__name__)

Emit = Callable[[Event], Awaitable[None]]


class CallSession:
    """Routes transcripts to whichever agent this act needs."""

    def __init__(self, settings: Settings, emit: Emit) -> None:
        self._settings = settings
        self._emit = emit
        self.act = "rescue"
        self.scenario: str | None = None
        self.mode = "live"
        self._rescue: RescueAgent | None = None
        self._guardian: Guardian | None = None

    # ------------------------------------------------------------- control

    async def set_act(self, act: str) -> None:
        if act == self.act and (self._rescue or self._guardian):
            return
        self.act = act
        log.info("act = %s", act)
        if act == "rescue":
            self._rescue = RescueAgent(self._settings, self._emit)
            await self._rescue.open()
        else:
            # Sandbox scenarios carry a known scammer number so the caller-series
            # rule has something to check. A live intercept would get this from
            # telephony metadata; there is no such leg in this build (§18).
            self._guardian = Guardian(
                self._emit, caller_number=_scenario_number(self.scenario)
            )

    def set_scenario(self, scenario: str) -> None:
        self.scenario = scenario
        if self._guardian is not None:
            self._guardian.caller_number = _scenario_number(scenario)

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    # ------------------------------------------------------------ speaker

    @property
    def speaker(self) -> str:
        """Who is talking into the mic right now.

        In intercept mode the audio being streamed is the scammer's (sandbox
        injection, §7.2). In rescue mode it is the victim.
        """
        return "scammer" if self.act == "intercept" else "victim"

    # ------------------------------------------------------- transcript in

    async def on_partial(self, text: str, t: float) -> None:
        await self._emit(TranscriptPartial(speaker=self.speaker, text=text, t=t))
        if self.act == "intercept" and self._guardian is not None:
            await self._guardian.on_caller_partial(text)

    async def on_final(self, text: str, t: float) -> None:
        await self._emit(TranscriptFinal(speaker=self.speaker, text=text, t=t))
        if self.act == "intercept":
            if self._guardian is not None:
                await self._guardian.on_caller_final(text)
        elif self._rescue is not None:
            await self._rescue.on_victim_final(text)

    async def on_vad(self, speaking: bool) -> None:
        """Local voice activity from the client.

        Only meaningful in intercept mode, and only once the guard is armed.
        The client has already muted by the time this arrives (§7.1) -- this
        records it and measures the loop.
        """
        if speaking and self.act == "intercept" and self._guardian is not None:
            await self._guardian.on_victim_speaking()

    @property
    def armed(self) -> bool:
        return bool(self._guardian and self._guardian.armed)

    def forensic_record(self) -> dict | None:
        return self._guardian.forensic_record() if self._guardian else None


def _scenario_number(scenario: str | None) -> str:
    """A plausible 10-digit mobile for each sandbox scenario.

    Deliberately NOT a 1600xx number: the whole point of the scenario is that a
    caller claiming to be a bank is calling from a line no bank may lawfully
    use. These are non-routable test numbers.
    """
    return {
        "kyc": "+917012345642",
        "arrest": "+919845003311",
        "electricity": "+918800774411",
    }.get(scenario or "", "+917012345642")
