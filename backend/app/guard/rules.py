"""Act 1 guard signals (CLAUDE.MD §4, §7.1, §13).

Every keyterm below was written against real STT output captured at Gate 0
(fixtures/stt_kyc_scammer.jsonl), not against the §15 scripts. That distinction
mattered: the scripts are Devanagari throughout, but Universal-3.6 Pro returns
code-switched text -- Hindi in Devanagari, English technical terms left in
Latin. The observed transcript is

    "मैडम जी, मैं SBI हेड ओफिस से बोल रहा हूँ।"
    "आपका KYC एक्स्पायर हो गया है।"
    "दो घंटे में अकाउंट ब्लॉक हो जाएगा, एक OTP आने वाला है, वो मुझे बोल दीजिए अभी."

so the OTP keyterm is the Latin "OTP", not "ओटीपी". A rule set written from the
script would have matched nothing at all. Devanagari spellings are kept as
secondary terms because STT output varies between runs, but Latin is primary.

Signals are scored, not boolean, because one of them is decisive on its own and
the rest are only suggestive together.
"""

import re
from dataclasses import dataclass

# The caller-number rule (§2). RBI requires regulated entities to make
# transactional calls from the 1600xx series -- circular of 17 Jan 2025,
# compliance due 31 Mar 2025. A caller claiming to be a bank from an ordinary
# 10-digit mobile cannot lawfully be that bank. No model is involved.
BANK_CALLER_PREFIX = "1600"


@dataclass(frozen=True, slots=True)
class Signal:
    name: str
    desc: str
    confidence: float
    score: int


def _any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(t.lower() in lowered for t in terms)


# --- observed at Gate 0: Latin, because STT leaves tech terms untranslated ---
OTP_TERMS = (
    "otp", "one time password", "one-time password", "passcode",
    "verification code", "ओटीपी", "कोड",
)
OTP_DEMAND_TERMS = (
    "बोल दीजिए", "बता दीजिए", "बोल दो", "बताओ", "share", "बताइए",
    "आने वाला है", "read out", "send me",
)

AUTHORITY_TERMS = (
    # Observed: "SBI हेड ओफिस" — brand in Latin, "head office" transliterated.
    "sbi", "hdfc", "icici", "axis", "bank", "बैंक", "हेड ओफिस", "head office",
    "cbi", "सीबीआई", "police", "पुलिस", "trai", "customs", "कस्टम",
    "income tax", "आयकर", "rbi", "आरबीआई",
)

URGENCY_TERMS = (
    # Observed: "दो घंटे में अकाउंट ब्लॉक हो जाएगा"
    "ब्लॉक हो जाएगा", "block हो", "blocked", "एक्स्पायर", "एक्सपायर",
    "expire", "expired", "तुरंत", "अभी", "immediately", "urgent",
    "कट जाएगा", "बंद हो", "आज रात", "deadline",
)

THREAT_TERMS = (
    "जेल", "गिरफ्तार", "arrest", "warrant", "वारंट", "case दर्ज",
    "money laundering", "मनी लॉन्ड्रिंग", "legal action", "कानूनी",
)

KYC_TERMS = ("kyc", "केवाईसी", "re-kyc", "verification", "वेरिफिकेशन")

# Digits as Gate 0 actually returned them: contiguous ASCII, e.g. "842190".
# Devanagari digits are included because a different run may produce them.
_DIGIT_RUN = re.compile(r"[0-9०-९]{4,}|[0-9०-९](?:[\s\-]+[0-9०-९]){3,}")


def evaluate(transcript: str, *, caller_number: str | None = None) -> list[Signal]:
    """Score one accumulated caller transcript.

    Returns the signals that fired. Confidence figures describe how reliably
    the pattern indicates fraud, not a model's certainty -- the caller-number
    check is 1.0 because it is a regulation, not a judgement.
    """
    signals: list[Signal] = []

    # Decisive on its own, and no LLM involved.
    if caller_number and _any(transcript, AUTHORITY_TERMS):
        digits = re.sub(r"\D", "", caller_number)
        if digits and not digits.startswith(BANK_CALLER_PREFIX):
            signals.append(
                Signal(
                    name="ILLEGAL_CALLER_SERIES",
                    desc=(
                        f"Caller claims a regulated entity but is calling from "
                        f"{caller_number}. RBI requires transactional calls from "
                        f"the 1600xx series (17 Jan 2025). A bank cannot lawfully "
                        f"have made this call."
                    ),
                    confidence=1.0,
                    score=60,
                )
            )

    if _any(transcript, OTP_TERMS) and _any(transcript, OTP_DEMAND_TERMS):
        signals.append(
            Signal(
                name="OTP_EXTRACTION_DEMAND",
                desc="Caller is asking the victim to read out a one-time code.",
                confidence=0.98,
                score=45,
            )
        )
    elif _any(transcript, OTP_TERMS):
        signals.append(
            Signal(
                name="OTP_MENTIONED",
                desc="A one-time code was mentioned by the caller.",
                confidence=0.70,
                score=20,
            )
        )

    if _any(transcript, AUTHORITY_TERMS):
        signals.append(
            Signal(
                name="AUTHORITY_SPOOF",
                desc="Caller claims to represent a bank or government body.",
                confidence=0.85,
                score=20,
            )
        )

    if _any(transcript, URGENCY_TERMS):
        signals.append(
            Signal(
                name="MANUFACTURED_URGENCY",
                desc="A deadline is being used to prevent the victim thinking.",
                confidence=0.88,
                score=18,
            )
        )

    if _any(transcript, THREAT_TERMS):
        signals.append(
            Signal(
                name="COERCIVE_THREAT",
                desc="Threat of arrest or legal action used to force compliance.",
                confidence=0.92,
                score=25,
            )
        )

    if _any(transcript, KYC_TERMS) and _any(transcript, URGENCY_TERMS):
        signals.append(
            Signal(
                name="KYC_EXPIRY_PRETEXT",
                desc="The 'your KYC has expired' pretext, India's most common opener.",
                confidence=0.90,
                score=15,
            )
        )

    return signals


def score(signals: list[Signal]) -> int:
    return min(100, sum(s.score for s in signals))


def state_for(total: int) -> str:
    """§9 threat states.

    The arm threshold is 'critical'. It sits at 60 so that the caller-number
    rule alone trips it -- an unlawful caller claiming to be a bank does not
    need corroboration -- while suggestive signals must stack to get there.
    """
    if total >= 60:
        return "critical"
    if total >= 30:
        return "suspicious"
    if total > 0:
        return "scanning"
    return "idle"


def contains_digits(text: str) -> bool:
    """Digits spoken. Evidence and display only -- NEVER the mute trigger.

    Gate 0 measured 1042-1125ms from first audio chunk to first partial. By the
    time this can return True the audio left the machine a full second ago,
    which is why §7.1 arms on the caller's turn and cuts the channel on local
    VAD instead.
    """
    return bool(_DIGIT_RUN.search(text))
