"""Gate 0, step 1 — generate Hinglish test audio with edge-tts.

CLAUDE.MD §19 forbids application code until Universal-3.5 Pro Streaming is
proven on real Hinglish. This script produces the audio that proof runs on.

Voices follow §5 VOICE CASTING: the scammer must be audibly distinct from the
agent so transcripts and demos never confuse the two.

Text is written in Devanagari with English tech terms left in Latin, per §13's
SCRIPT RULE. That rule exists for TTS quality, but it also mirrors what
AssemblyAI's own multilingual docs show code-switched Hindi looking like on the
way back out — which is what Gate 0 question 1 is checking.

Output: fixtures/audio/*.mp3 (24kHz mono MP3, edge-tts' native format).
"""

import asyncio
from pathlib import Path

import edge_tts

# §5 VOICE CASTING
VOICE_SCAMMER = "hi-IN-MadhurNeural"  # male
VOICE_VICTIM = "hi-IN-SwaraNeural"  # female

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "audio"

# §15 SCENARIO SCRIPTS, verbatim, plus one line Gate 0 needs that §15 does not
# provide: a victim actually speaking OTP digits. Without spoken digits there is
# nothing to test word-timestamp targeting against, which is Gate 0 question 2.
CLIPS: list[tuple[str, str, str]] = [
    (
        "kyc_scammer",
        VOICE_SCAMMER,
        "मैडम जी, मैं SBI head office से बोल रहा हूँ। आपका KYC expire हो गया है। "
        "2 घंटे में account block हो जाएगा — एक OTP आने वाला है, वो मुझे बोल दीजिए अभी।",
    ),
    (
        "arrest_scammer",
        VOICE_SCAMMER,
        "आपके नाम पे money-laundering case है। CBI officer से video call पे बात करो, वरना जेल।",
    ),
    (
        "electricity_scammer",
        VOICE_SCAMMER,
        "आपकी बिजली आज रात 9 बजे कट जाएगी। payment link पे तुरंत pay करो।",
    ),
    # Digit-bearing line — the bleep-targeting probe.
    (
        "victim_otp_digits",
        VOICE_VICTIM,
        "मेरा OTP 8 4 2 1 9 0 है।",
    ),
    # §15 rescue victim line — drives the Act 2 panic call.
    (
        "victim_panic",
        VOICE_VICTIM,
        "किसी ने bank officer बन के कहा KYC expire है... मैंने OTP दे दिया, 40 हज़ार कट गए।",
    ),
]


async def synth(name: str, voice: str, text: str) -> Path:
    out = FIXTURES / f"{name}.mp3"
    await edge_tts.Communicate(text, voice).save(str(out))
    return out


async def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, voice, text in CLIPS:
        path = await synth(name, voice, text)
        print(f"  {path.name:26} {voice:20} {path.stat().st_size:>7,} bytes")
    print(f"\n{len(CLIPS)} clips written to {FIXTURES}")


if __name__ == "__main__":
    asyncio.run(main())
