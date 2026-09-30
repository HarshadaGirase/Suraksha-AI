"""Replay the Gate 0 fixture through the guard (CLAUDE.MD §19 batch D).

This uses the transcripts AssemblyAI actually returned, not the §15 scripts.
The distinction is the point of the test: the scripts are pure Devanagari, the
real output is code-switched, and a rule set written from the scripts matches
nothing.

No AssemblyAI credit is spent -- the fixture was captured once at Gate 0.

    backend/.venv/bin/python ../scripts/test_guard.py
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.guard.guardian import Guardian  # noqa: E402

FIXTURES = ROOT / "fixtures"

# A scammer calling from an ordinary mobile while claiming to be SBI. RBI
# requires 1600xx for bank transactional calls, so this alone is decisive.
SCAMMER_NUMBER = "+917012345642"


def finals(path: Path) -> list[str]:
    out = []
    for line in path.read_text().splitlines():
        msg = json.loads(line)
        if msg.get("kind") == "Turn" and msg.get("end_of_turn") and msg.get("transcript"):
            out.append(msg["transcript"])
    return out


EVENTS: list[dict] = []


async def emit(event) -> None:
    payload = event.dump()
    EVENTS.append(payload)
    kind = payload["type"]
    if kind == "threat.update":
        print(f"    threat {payload['score']:3d}  {payload['state']}")
    elif kind == "evidence.update":
        for s in payload["signals"]:
            print(f"      + {s['name']} ({s['confidence']:.0%})")
    elif kind == "guard.action":
        print(f"    ACTION {payload['action']} ({payload['ms']}ms)")
    elif kind == "stat.update":
        print(f"    STAT {payload['key']} = {payload['value']}")


async def main() -> int:
    caller = finals(FIXTURES / "stt_kyc_scammer.jsonl")
    victim = finals(FIXTURES / "stt_victim_otp_digits.jsonl")
    if not caller or not victim:
        print("fixtures missing — run scripts/gate0_stream.py first")
        return 1

    g = Guardian(emit, caller_number=SCAMMER_NUMBER)

    print("CALLER (real STT output):")
    for turn in caller:
        print(f"  {turn}")
        await g.on_caller_final(turn)

    print(f"\n  armed after caller turns: {g.armed}")
    if not g.armed:
        print("\nFAIL: guard never armed on a textbook KYC/OTP scam")
        return 1

    print("\nVICTIM starts to speak — local VAD fires:")
    await g.on_victim_speaking()

    # Deliberately NOT replaying the victim clip through on_victim_final here:
    # the cut is in place, so in a real call that audio never reaches STT. The
    # leak path is exercised separately below.
    print("\n  (victim audio is muted at source — nothing reaches STT)")

    record = g.forensic_record(case_id="GH-TEST")
    print("\n" + "=" * 62)
    print(json.dumps(record, ensure_ascii=False, indent=2))

    ok = True
    names = {s["name"] for s in record["signals"]}
    for required in ("ILLEGAL_CALLER_SERIES", "OTP_EXTRACTION_DEMAND"):
        if required not in names:
            print(f"\nFAIL: {required} did not fire")
            ok = False
    if not record["channel_cut"]:
        print("\nFAIL: channel was never cut")
        ok = False
    if not record["victim_speech_blocked"]:
        print("\nFAIL: victim speech was not blocked")
        ok = False
    if record["digits_leaked_to_stt"]:
        print("\nFAIL: digits reached STT — the cut did not hold")
        ok = False
    if record["amount_lost"] != 0:
        print("\nFAIL: amount_lost should be 0 on a successful intercept")
        ok = False

    # The failure path: if the cut never happened, digits DO arrive and must be
    # recorded as a leak rather than quietly ignored.
    leak = Guardian(lambda e: None, caller_number=SCAMMER_NUMBER)
    for turn in caller:
        await leak.on_caller_final(turn)
    for turn in victim:
        await leak.on_victim_final(turn)
    lrec = leak.forensic_record()
    if not lrec["digits_leaked_to_stt"] or lrec["amount_lost"] == 0:
        print("\nFAIL: an uncut call must not report a clean intercept")
        ok = False
    else:
        print("uncut control: digits recorded as leaked, no ₹0 claim made")

    # A legitimate bank on 1600xx must NOT trip the decisive rule.
    clean = Guardian(emit, caller_number="1600123456")
    for turn in caller:
        await clean.on_caller_final(turn)
    clean_names = {s["name"] for s in clean.forensic_record()["signals"]}
    if "ILLEGAL_CALLER_SERIES" in clean_names:
        print("\nFAIL: 1600xx caller wrongly flagged as illegal series")
        ok = False
    else:
        print("\n1600xx control: ILLEGAL_CALLER_SERIES correctly not raised")

    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
