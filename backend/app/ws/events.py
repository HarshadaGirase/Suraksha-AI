"""WS#1 event contract (CLAUDE.MD §9).

§16's BLANK-STATE POLICY says the client renders ONLY from these messages and
never pre-fills a value. That makes this module the contract between backend
and frontend: if a number appears in the UI, it arrived in one of these.

Helper constructors are used rather than raw dicts so a typo in an event name
fails here instead of silently rendering nothing in the browser.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- server -> client


class Event(BaseModel):
    """Base for every server->client message."""

    type: str

    def dump(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ConnectionStatus(Event):
    type: Literal["connection.status"] = "connection.status"
    service: Literal["stt", "gemini", "pgvector", "tts"]
    state: Literal["standby", "online", "error"]


class TranscriptPartial(Event):
    type: Literal["transcript.partial"] = "transcript.partial"
    speaker: Literal["scammer", "victim", "agent"]
    text: str
    t: float


class TranscriptFinal(Event):
    type: Literal["transcript.final"] = "transcript.final"
    speaker: Literal["scammer", "victim", "agent"]
    text: str
    t: float


class WordTs(Event):
    """Word-level timing. Per PLAN.md C1 this feed is for evidence and display
    only — it describes audio already sent, so it must never be the trigger
    for muting the outbound channel."""

    type: Literal["word.ts"] = "word.ts"
    word: str
    start: float
    end: float


class ThreatUpdate(Event):
    type: Literal["threat.update"] = "threat.update"
    score: int = 0
    state: Literal["idle", "scanning", "suspicious", "critical"] = "idle"


class EvidenceSignal(BaseModel):
    name: str
    desc: str
    confidence: float


class EvidenceUpdate(Event):
    type: Literal["evidence.update"] = "evidence.update"
    signals: list[EvidenceSignal] = Field(default_factory=list)


class GuardAction(Event):
    type: Literal["guard.action"] = "guard.action"
    action: Literal[
        "guard_rules",
        "counter_interrogate",
        "bleep_otp",
        "terminate_call",
        "warning_tts",
    ]
    ms: int


class ToolCall(Event):
    type: Literal["tool.call"] = "tool.call"
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(Event):
    type: Literal["tool.result"] = "tool.result"
    name: str
    ms: int
    result: dict[str, Any] = Field(default_factory=dict)


class CaseUpdate(Event):
    type: Literal["case.update"] = "case.update"
    case_id: str
    fraud_type: str | None = None
    confidence: float | None = None
    amount: int | None = None
    app: str | None = None
    when_ago: str | None = None
    district: str | None = None


class DocReady(Event):
    """§16: download only. There is deliberately no 'submitted' event in this
    contract, and §12 has no 'submitted' status — the victim files manually."""

    type: Literal["doc.ready"] = "doc.ready"
    doc: Literal["1930", "freeze", "forensic"]
    download_url: str
    citation: str | None = None


class TtsPlay(Event):
    type: Literal["tts.play"] = "tts.play"
    url: str


class StatUpdate(Event):
    type: Literal["stat.update"] = "stat.update"
    key: Literal["guard_loop", "rescue_loop", "redaction", "stt_latency"]
    value: str


class ErrorEvent(Event):
    type: Literal["error"] = "error"
    message: str


# ---------------------------------------------------------------- client -> server


class ModeMessage(BaseModel):
    type: Literal["mode"]
    mode: Literal["sandbox", "live"]


class ScenarioMessage(BaseModel):
    type: Literal["scenario"]
    id: Literal["kyc", "arrest", "electricity"]


class ActMessage(BaseModel):
    type: Literal["act"]
    act: Literal["intercept", "rescue"]


CLIENT_MESSAGES = {
    "mode": ModeMessage,
    "scenario": ScenarioMessage,
    "act": ActMessage,
}


def parse_client_message(raw: dict[str, Any]) -> BaseModel | None:
    """Return a validated client message, or None if unrecognised.

    Unknown messages are dropped rather than raised: a stray frame from a
    reconnecting browser must not tear down a live call.
    """
    model = CLIENT_MESSAGES.get(raw.get("type", ""))
    if model is None:
        return None
    try:
        return model(**raw)
    except Exception:
        return None
