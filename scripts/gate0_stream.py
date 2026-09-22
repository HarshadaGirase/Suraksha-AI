"""Gate 0, step 2 — prove Universal-3.5 Pro Streaming on real Hinglish.

CLAUDE.MD §19 makes this the stop-the-line gate: if code-mixed Hindi does not
transcribe cleanly, everything downstream is built on sand and the plan changes.

Three questions this answers, each of which blocks real code:

  Q1  Does Hindi come back in Devanagari or romanized Latin?
      Decides whether every guard keyterm is "ओटीपी" or "OTP batao". Not one
      guard rule can be written before this is observed. (PLAN.md C7)

  Q2  Do words[] timestamps arrive on PARTIAL turns, or only on finals?
      Decides whether live per-word redaction is possible at all. Note that
      even on partials the timestamp describes audio already sent — see
      PLAN.md C1 for why the guard must mute predictively rather than react
      to this feed.

  Q3  What is the real latency to first partial?
      Replaces the guessed 280ms in §7's pipeline diagram.

Every raw message is written to fixtures/stt_hinglish.jsonl. That file becomes
the fixture the guard layer and the backend tests are built against, so the
rest of the build never needs to spend credit re-asking these questions.

Usage:  python scripts/gate0_stream.py [clip_name]     (default: kyc_scammer)
"""

import asyncio
import json
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr
from dotenv import load_dotenv
from assemblyai.streaming.v3 import (
    AsyncRealTimeTranscriber,
    BeginEvent,
    Encoding,
    RealTimeError,
    RealTimeEvents,
    RealTimeParameters,
    RealTimeTranscriberOptions,
    TerminationEvent,
    TurnEvent,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
AUDIO = FIXTURES / "audio"

# §7.3 — AssemblyAI Realtime takes 16kHz PCM16 mono. The browser AudioWorklet
# will produce exactly this, so Gate 0 must test the production format. The
# docs quickstart uses AAC; deliberately not following it here.
TARGET_SR = 16_000
CHUNK_MS = 100  # API accepts 50–1000ms

DEVANAGARI = range(0x0900, 0x0980)


def load_pcm16(path: Path) -> bytes:
    """MP3 -> 16kHz mono PCM16. soundfile bundles libsndfile, soxr resamples,
    so no system ffmpeg is required anywhere in this project."""
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)  # edge-tts is already mono; defensive
    if sr != TARGET_SR:
        mono = soxr.resample(mono, sr, TARGET_SR)
    clipped = np.clip(mono, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def describe_script(text: str) -> str:
    """Q1 — classify the script actually returned."""
    deva = sum(1 for c in text if ord(c) in DEVANAGARI)
    latin = sum(1 for c in text if c.isalpha() and ord(c) < 128)
    if deva and latin:
        return f"MIXED — {deva} Devanagari + {latin} Latin chars (code-switched)"
    if deva:
        return f"DEVANAGARI — {deva} chars"
    if latin:
        return f"LATIN only — {latin} chars (Hindi was romanized or lost)"
    return "indeterminate"


async def run(clip: str) -> int:
    load_dotenv(ROOT / ".env")
    import os

    key = os.environ.get("ASSEMBLYAI_API_KEY", "")
    if not key or key == "your_key_here":
        print("ASSEMBLYAI_API_KEY is not set in .env — cannot run Gate 0.")
        return 2

    src = AUDIO / f"{clip}.mp3"
    if not src.exists():
        print(f"missing {src} — run scripts/gate0_tts.py first")
        return 2

    pcm = load_pcm16(src)
    bytes_per_chunk = int(TARGET_SR * CHUNK_MS / 1000) * 2
    duration = len(pcm) / 2 / TARGET_SR
    print(f"clip     : {clip}.mp3  ({duration:.1f}s, {len(pcm):,} bytes PCM16 @ {TARGET_SR}Hz)")

    events: list[dict] = []
    timing: dict[str, float] = {}

    def record(kind: str, payload: dict) -> None:
        events.append({"kind": kind, "at": time.time(), **payload})

    def on_begin(_c, e: BeginEvent) -> None:
        timing["begin"] = time.time()
        print(f"session  : {e.id}")

    def on_turn(_c, e: TurnEvent) -> None:
        now = time.time()
        if e.transcript and "first_transcript" not in timing:
            timing["first_transcript"] = now
        record(
            "Turn",
            {
                "turn_order": e.turn_order,
                "end_of_turn": e.end_of_turn,
                "turn_is_formatted": e.turn_is_formatted,
                "transcript": e.transcript,
                "language_code": e.language_code,
                "language_confidence": e.language_confidence,
                "words": [w.model_dump() for w in (e.words or [])],
            },
        )
        tag = "FINAL  " if e.end_of_turn else "partial"
        nwords = len(e.words or [])
        print(f"  {tag} w={nwords:<3} {e.transcript[:88]}")

    def on_term(_c, e: TerminationEvent) -> None:
        record("Termination", {"audio_duration_seconds": e.audio_duration_seconds})

    def on_err(_c, err: RealTimeError) -> None:
        record("Error", {"error": str(err)})
        print(f"  ERROR: {err}")

    client = AsyncRealTimeTranscriber(
        RealTimeTranscriberOptions(terminate_timeout=15.0), api_key=key
    )
    client.on(RealTimeEvents.Begin, on_begin)
    client.on(RealTimeEvents.Turn, on_turn)
    client.on(RealTimeEvents.Termination, on_term)
    client.on(RealTimeEvents.Error, on_err)

    # language_codes=["en","hi"] + language_detection is the documented way to
    # steer code-switched audio. The singular language_code is for genuinely
    # monolingual sessions and would break Hinglish — deliberately unset.
    params = RealTimeParameters(
        speech_model="universal-3-5-pro",
        encoding=Encoding.pcm_s16le,
        sample_rate=TARGET_SR,
        language_codes=["en", "hi"],
        language_detection=True,
        format_turns=True,
        include_partial_turns=True,
    )

    await client.connect(params)
    timing["first_chunk"] = time.time()

    # Pace at real time. The API warns that blasting a pre-recorded file
    # produces inconsistent Turn messages, which would corrupt the very
    # timestamps Q2 is measuring.
    for i in range(0, len(pcm), bytes_per_chunk):
        await client.stream(pcm[i : i + bytes_per_chunk])
        await asyncio.sleep(CHUNK_MS / 1000)

    await asyncio.sleep(1.5)  # let the final turn land
    await client.disconnect(terminate=True)

    out = FIXTURES / f"stt_{clip}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # ---- Gate 0 verdict -------------------------------------------------
    turns = [e for e in events if e["kind"] == "Turn"]
    partials = [t for t in turns if not t["end_of_turn"]]
    finals = [t for t in turns if t["end_of_turn"]]
    best = (finals or turns or [{}])[-1].get("transcript", "")

    partials_with_words = [t for t in partials if t["words"]]

    print("\n" + "=" * 72)
    print("GATE 0 VERDICT")
    print("=" * 72)
    print(f"transcript : {best}")
    print(f"\nQ1 script  : {describe_script(best)}")
    print(
        f"Q2 partials: {len(partials)} partial turns, "
        f"{len(partials_with_words)} carried words[] timestamps"
    )
    if partials_with_words:
        w = partials_with_words[0]["words"][0]
        print(f"             e.g. {w['text']!r} start={w['start']}ms end={w['end']}ms")
    if "first_transcript" in timing:
        ms = (timing["first_transcript"] - timing["first_chunk"]) * 1000
        print(f"Q3 latency : {ms:.0f}ms  first chunk -> first transcript")
    langs = {t["language_code"] for t in turns if t.get("language_code")}
    print(f"languages  : {langs or 'not reported'}")
    print(f"\nraw events -> {out.relative_to(ROOT)}  ({len(events)} messages)")
    return 0


if __name__ == "__main__":
    clip = sys.argv[1] if len(sys.argv) > 1 else "kyc_scammer"
    raise SystemExit(asyncio.run(run(clip)))
