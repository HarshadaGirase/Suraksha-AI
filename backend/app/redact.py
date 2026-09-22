"""Digit redaction before persistence (PLAN.md C4).

CLAUDE.MD §10.1 claims "The call NEVER collects PII", but §12 stores the whole
panic call in cases.transcript. A victim who blurts an OTP, a card number or an
account number puts it straight into the database and contradicts the claim.

So raw transcripts are redacted here before anything is written down. The live
guard path still sees unredacted text — it has to, to detect an OTP demand —
but nothing unredacted is persisted.

Two shapes matter, because STT renders spoken digits both ways:
  "842190"        -> contiguous run
  "8 4 2 1 9 0"   -> separated, which is how people actually read out an OTP

Devanagari digits are included: Hindi STT output may use ०-९.
"""

import re

# ASCII 0-9 plus Devanagari ०-९
_D = r"[0-9०-९]"

# 4+ contiguous digits.
_CONTIGUOUS = re.compile(rf"{_D}{{4,}}")

# 4+ digits separated by spaces or hyphens, e.g. "8 4 2 1 9 0" or "8-4-2-1".
_SEPARATED = re.compile(rf"{_D}(?:[\s\-]+{_D}){{3,}}")

MASK = "•" * 6  # ••••••

# Numbers that are public helplines, not credentials. 1930 is the national
# cyber-fraud helpline (§2) and appears in almost every rescue transcript and
# in the closing agent line — masking it would corrupt the 1930 draft itself.
ALLOWLIST = {"1930", "112", "155260"}

_SEPARATORS = re.compile(r"[\s\-]+")
_DEVA_TO_ASCII = str.maketrans("०१२३४५६७८९", "0123456789")


def _normalise(run: str) -> str:
    """Strip separators and fold Devanagari digits, so '1 9 3 0' and '१९३०'
    both compare equal to '1930'."""
    return _SEPARATORS.sub("", run).translate(_DEVA_TO_ASCII)


def _mask_unless_allowed(match: re.Match[str], mask: str) -> str:
    return match.group(0) if _normalise(match.group(0)) in ALLOWLIST else mask


def redact_digits(text: str, mask: str = MASK) -> str:
    """Replace digit runs of length >= 4 with a mask.

    Short numbers survive deliberately: "2 ghante" and "40 hazaar" are
    load-bearing for classification and for the 1930 draft's amount field.
    A 4-digit threshold keeps those while catching OTPs, card and account
    numbers. Public helpline numbers are allowlisted.

    >>> redact_digits("मेरा OTP 8 4 2 1 9 0 है")
    'मेरा OTP •••••• है'
    >>> redact_digits("40 हज़ार कट गए")
    '40 हज़ार कट गए'
    >>> redact_digits("1930 पे file कर दीजिए")
    '1930 पे file कर दीजिए'
    """
    if not text:
        return text

    def sub(m: re.Match[str]) -> str:
        return _mask_unless_allowed(m, mask)

    # Separated first: the contiguous pattern would otherwise leave the
    # single digits of "8 4 2 1 9 0" untouched.
    text = _SEPARATED.sub(sub, text)
    return _CONTIGUOUS.sub(sub, text)


def contains_digit_run(text: str) -> bool:
    """True if text holds a digit run long enough to be a credential.

    Used by the guard layer as one signal that the victim has started reading
    something out. It is NOT the mute trigger — see PLAN.md C1: by the time
    this returns True the audio has already left the client.
    """
    for pattern in (_SEPARATED, _CONTIGUOUS):
        for m in pattern.finditer(text):
            if _normalise(m.group(0)) not in ALLOWLIST:
                return True
    return False
