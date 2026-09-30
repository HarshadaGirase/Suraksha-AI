"""Drive Act 2 end to end without AssemblyAI (CLAUDE.MD §19 batch B).

Feeds a scripted victim conversation straight into the orchestrator, standing
in for transcript.final events. Real Gemini, real Postgres, zero streaming
credit — which is the point: the whole rescue flow can be developed and
regression-tested without touching the AssemblyAI balance.

    backend/.venv/bin/python ../scripts/test_rescue.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.agents.rescue import RescueAgent  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import pool  # noqa: E402

# §15 rescue victim line, then the answers to the agent's follow-ups. The OTP
# turn is deliberate: it must be refused, not transcribed.
TURNS = [
    "किसी ने bank officer बन के कहा KYC expire है... मैंने OTP दे दिया, 40 हज़ार कट गए।",
    "PhonePe से गए, बीस मिनट पहले",
    "मेरा OTP 8 4 2 1 9 0 था",          # <- must be refused
    "transaction ID 427219883901 है",
    "Bhopal, MP से हूँ",
]

EVENTS: list[dict] = []


async def emit(event) -> None:
    payload = event.dump()
    EVENTS.append(payload)
    kind = payload["type"]
    if kind == "tool.call":
        print(f"  -> {payload['name']}({json.dumps(payload['args'], ensure_ascii=False)})")
    elif kind == "tool.result":
        print(f"  <- {payload['name']} {payload['ms']}ms {json.dumps(payload['result'], ensure_ascii=False)}")
    elif kind == "case.update":
        print(f"  CASE {payload['case_id']}: {payload.get('fraud_type')} "
              f"₹{payload.get('amount')} {payload.get('app')} {payload.get('district')}")
    elif kind == "doc.ready":
        print(f"  DOC READY: {payload['doc']} -> {payload['download_url']}")
    elif kind == "stat.update":
        print(f"  STAT {payload['key']} = {payload['value']}")
    elif kind == "transcript.final" and payload["speaker"] == "agent":
        print(f"  AGENT: {payload['text']}")
    elif kind == "error":
        print(f"  ERROR: {payload['message']}")


async def main() -> int:
    settings = get_settings()
    if not settings.has_gemini:
        print("GEMINI_API_KEY not set")
        return 1

    await pool.connect(settings)
    agent = RescueAgent(settings, emit)
    await agent.open()

    for turn in TURNS:
        print(f"\nVICTIM: {turn}")
        await agent.on_victim_final(turn)

    s = agent.state
    print("\n" + "=" * 60)
    print(f"case_id   : {s.case_id}")
    print(f"fraud     : {s.fraud_type} ({s.confidence})")
    print(f"amount    : {s.amount}")
    print(f"app       : {s.app}")
    print(f"utr       : {s.utr}")
    print(f"when_ago  : {s.when_ago}")
    print(f"district  : {s.district}")
    print(f"missing   : {s.missing_fields}")
    print(f"elapsed   : {s.clock.format()}")
    print(f"gemini calls: {agent._agent.calls_made}")

    print("\n-- stored transcript (must contain no OTP) --")
    for line in s.transcript:
        print("  ", line)

    ok = True
    if any("842190" in json.dumps(l, ensure_ascii=False) for l in s.transcript):
        print("\nFAIL: OTP leaked into the transcript")
        ok = False
    if not any(e["type"] == "doc.ready" for e in EVENTS):
        print("\nFAIL: no doc.ready emitted")
        ok = False
    if s.draft and s.draft.get("utr") != "427219883901":
        print(f"\nFAIL: UTR lost — got {s.draft.get('utr')!r}")
        ok = False

    if s.draft:
        print("\n-- draft --")
        print(json.dumps(s.draft, ensure_ascii=False, indent=2))

    await pool.disconnect()
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
