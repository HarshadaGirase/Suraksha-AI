"""Tool implementations (CLAUDE.MD §10).

Gemini decides WHICH tool to call and with what arguments. These functions do
the work and own every side effect -- the database write, the case id, the
clock. Nothing here trusts the model with a fact it could have invented: the
case id is generated locally, the timestamps are the server's, and the status
is set by us.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.agents.clock import RescueClock
from app.db import cases as repo

log = logging.getLogger(__name__)

# Asked in this order. The UTR is second because CFCFRMS needs it to trace the
# money and a complaint without one stalls -- but the rail has to be known
# first for the question to make sense to the victim.
ASK_ORDER = ("app", "utr", "when_ago", "district", "suspect_number")

ASK_PHRASES = {
    "app": "पैसे PhonePe से गए या GPay से?",
    "utr": "आपके phone में उस transaction का ID दिख रहा है? वो complaint के लिए सबसे important है।",
    "when_ago": "यह कितनी देर पहले हुआ?",
    "district": "आप किस city या district से हैं?",
    "suspect_number": "जिस number से call आया था, वो अभी भी आपके phone में है?",
}


@dataclass
class RescueState:
    """Everything known about this conversation so far.

    A field only moves from None once the victim has actually said it, so
    `missing_fields` is the literal list of questions still to ask (§10.1).
    """

    case_id: str | None = None
    fraud_type: str | None = None
    confidence: float | None = None
    amount: int | None = None
    app: str | None = None
    utr: str | None = None
    when_ago: str | None = None
    district: str | None = None
    suspect_number: str | None = None
    language_code: str | None = None
    language_confidence: float | None = None
    transcript: list[dict[str, Any]] = field(default_factory=list)
    clock: RescueClock = field(default_factory=RescueClock)
    asked: set[str] = field(default_factory=set)
    draft: dict[str, Any] | None = None

    @property
    def missing_fields(self) -> list[str]:
        return [f for f in ASK_ORDER if getattr(self, f) is None]

    def next_question(self) -> tuple[str, str] | None:
        """The next field to ask about, or None when nothing is left.

        Each field is asked at most once. A victim who does not have their UTR
        to hand will not acquire one by being asked three times, and the
        complaint is still filable with the field blank.
        """
        for f in self.missing_fields:
            if f not in self.asked:
                self.asked.add(f)
                return f, ASK_PHRASES[f]
        return None

    def ready_to_draft(self) -> bool:
        """Enough to produce a usable complaint, and nothing left to ask.

        Both halves matter. Drafting on the first two facts produced a document
        with utr and district blank because those answers arrived two turns
        later. Waiting for every field to be *filled* would be worse -- a
        victim who cannot find their UTR would get no document at all -- so the
        bar is that every question has been ASKED, not answered.
        """
        if not (self.case_id and self.fraud_type and self.amount is not None):
            return False
        return all(f in self.asked for f in self.missing_fields)


async def classify_fraud(state: RescueState, args: dict[str, Any]) -> dict[str, Any]:
    state.fraud_type = args.get("fraud_type")
    state.confidence = args.get("confidence")
    return {"fraud_type": state.fraud_type, "confidence": state.confidence}


async def extract_entities(state: RescueState, args: dict[str, Any]) -> dict[str, Any]:
    """Merge newly-heard facts.

    Only non-null values are applied. A later turn returning null for a field
    the victim already answered must not erase it -- that would make the agent
    ask the same question twice and look like it was not listening.
    """
    applied: dict[str, Any] = {}
    for key in ("amount", "app", "utr", "when_ago", "district", "suspect_number"):
        value = args.get(key)
        if value is not None and getattr(state, key) is None:
            setattr(state, key, value)
            applied[key] = value

    if state.case_id and applied:
        await repo.update_case(state.case_id, **applied)

    # A field can land after the draft was built. Refresh the structured part
    # from state -- no model call, because the narrative has not changed and
    # regenerating it would risk the model rewriting facts it already got right.
    if state.draft is not None and applied:
        state.draft.update(applied)
        state.draft["missing_fields"] = state.missing_fields
        if state.case_id:
            await repo.update_case(state.case_id, draft=state.draft)

    return {
        "applied": applied,
        "still_missing": state.missing_fields,
    }


async def create_case(state: RescueState, args: dict[str, Any]) -> dict[str, Any]:
    """Open the case record and start the clock.

    Idempotent: the model sometimes calls this twice across turns, and a second
    case id would orphan the first record and reset the clock mid-demo.
    """
    if state.case_id:
        return {"case_id": state.case_id, "already_open": True}

    state.fraud_type = args.get("fraud_type") or state.fraud_type
    if args.get("amount") is not None and state.amount is None:
        state.amount = args["amount"]
    if args.get("app") and state.app is None:
        state.app = args["app"]

    state.case_id = repo.new_case_id()
    state.clock.start()

    await repo.create_case(
        case_id=state.case_id,
        act="rescue",
        fraud_type=state.fraud_type,
        confidence=state.confidence,
        amount=state.amount,
        app=state.app,
        utr=state.utr,
        when_ago=state.when_ago,
        district=state.district,
        suspect_number=state.suspect_number,
        language_code=state.language_code,
        language_confidence=state.language_confidence,
        transcript=state.transcript,
    )
    log.info("case %s opened", state.case_id)
    return {"case_id": state.case_id}


async def draft_1930_report(state: RescueState, args: dict[str, Any]) -> dict[str, Any]:
    """Assemble the complaint draft.

    The model supplies only the Hindi narrative. Every structured field comes
    from state, i.e. from something the victim actually said, so the model
    cannot introduce an amount or a UTR that was never spoken.
    """
    if not state.case_id:
        return {"error": "no case open"}

    state.draft = {
        "case_id": state.case_id,
        "category": "Online Financial Fraud",
        "sub_category": _sub_category(state.fraud_type),
        "fraud_type": state.fraud_type,
        "confidence": state.confidence,
        "amount": state.amount,
        "app": state.app,
        "utr": state.utr,
        "when_ago": state.when_ago,
        "district": state.district,
        "suspect_number": state.suspect_number,
        "victim_statement_hi": args.get("victim_statement_hi", ""),
        # §10.1 — rendered as blank labelled fields. The call never collects
        # any of these, which is the privacy claim made real.
        "fill_at_filing": [
            "Name", "Mobile", "Email", "Address",
            "Bank / account details", "Government ID",
            "14-digit acknowledgement number (you get this AFTER filing)",
        ],
        "missing_fields": state.missing_fields,
        "elapsed": state.clock.format(),
    }

    # Persisted so the download survives the call ending — the victim opens the
    # PDF after they have hung up, not during.
    await repo.update_case(
        state.case_id, status="documents_ready", draft=state.draft
    )
    return {
        "case_id": state.case_id,
        "fields_filled": sum(
            1 for k in ("amount", "app", "utr", "when_ago", "district", "suspect_number")
            if getattr(state, k) is not None
        ),
        "fields_blank": len(state.missing_fields),
        "elapsed": state.draft["elapsed"],
    }


def _sub_category(fraud_type: str | None) -> str:
    """Map our taxonomy onto the categories NCRP's own form offers."""
    return {
        "kyc_expiry_otp": "UPI / Internet Banking fraud",
        "otp_screen_share": "UPI / Internet Banking fraud",
        "upi_collect": "UPI / Internet Banking fraud",
        "digital_arrest": "Impersonation of government authority",
        "parcel_customs": "Impersonation of government authority",
        "electricity_disconnect": "Fake utility / service provider",
        "investment_task": "Investment / task-based fraud",
        "loan_app_harassment": "Fraudulent loan application",
    }.get(fraud_type or "", "Other online financial fraud")


EXECUTORS = {
    "classify_fraud": classify_fraud,
    "extract_entities": extract_entities,
    "create_case": create_case,
    "draft_1930_report": draft_1930_report,
}
