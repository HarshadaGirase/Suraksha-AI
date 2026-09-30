"""The four Gemini tools (CLAUDE.MD §10).

Exactly four, in this order: classify_fraud -> extract_entities ->
create_case -> draft_1930_report. draft_freeze_letter was removed in the
2026-09-30 revision.

Every optional field is nullable and stays null when the victim has not said
it. §10.1: "A field that was not spoken stays empty and the agent asks for it
aloud." A complaint with a hallucinated UTR is worse than one with a blank UTR
-- it gets rejected at the counter and the victim loses the window -- so the
schemas describe absence as a valid answer rather than something to avoid.
"""

# §10 taxonomy. Closed set: the classifier picks a label, it does not invent one.
FRAUD_TYPES = [
    "digital_arrest",
    "kyc_expiry_otp",
    "parcel_customs",
    "electricity_disconnect",
    "investment_task",
    "upi_collect",
    "otp_screen_share",
    "loan_app_harassment",
]

# Payment rails a victim actually names out loud in India.
PAYMENT_APPS = [
    "PhonePe", "GPay", "Paytm", "BHIM", "Amazon Pay", "WhatsApp Pay",
    "Net Banking", "Debit Card", "Credit Card", "Other",
]

CLASSIFY_FRAUD = {
    "name": "classify_fraud",
    "description": (
        "Classify a reported scam transcript into India's fraud taxonomy. "
        "Call this as soon as the victim has described what happened."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "fraud_type": {
                "type": "STRING",
                "enum": FRAUD_TYPES,
                "description": "The closest matching category.",
            },
            "confidence": {
                "type": "NUMBER",
                "description": (
                    "0.0-1.0. Report genuine uncertainty; a low number is a "
                    "useful signal, an inflated one is not."
                ),
            },
        },
        "required": ["fraud_type", "confidence"],
    },
}

EXTRACT_ENTITIES = {
    "name": "extract_entities",
    "description": (
        "Pull the complaint facts out of what the victim has actually said. "
        "Leave a field null if it was not stated -- never guess, never infer "
        "from context. The agent will ask the victim aloud for anything null."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "amount": {
                "type": "INTEGER", "nullable": True,
                "description": (
                    "Rupees lost, as an integer. '40 hazaar' is 40000, "
                    "'do lakh' is 200000. Null if not stated."
                ),
            },
            "app": {
                "type": "STRING", "nullable": True,
                "enum": PAYMENT_APPS,
                "description": "Payment rail used. Null if not stated.",
            },
            "utr": {
                "type": "STRING", "nullable": True,
                "description": (
                    "Transaction ID / UTR / reference number, digits only. "
                    "This is the single most important field for the "
                    "complaint. Null if not stated -- never construct one."
                ),
            },
            "when_ago": {
                "type": "STRING", "nullable": True,
                "description": (
                    "How long ago, in the victim's own words, e.g. '22 min', "
                    "'2 ghante'. Null if not stated."
                ),
            },
            "district": {
                "type": "STRING", "nullable": True,
                "description": (
                    "District and state, only if the victim states it. Do NOT "
                    "infer from language, accent or bank name."
                ),
            },
            "suspect_number": {
                "type": "STRING", "nullable": True,
                "description": (
                    "Phone number the scammer called from, if the victim "
                    "reads it out. Null otherwise."
                ),
            },
        },
        "required": [],
    },
}

CREATE_CASE = {
    "name": "create_case",
    "description": (
        "Open the case record and start the clock. Call this once the fraud "
        "type and at least the amount are known -- do not wait for every "
        "field, because the remaining ones are collected while the case is "
        "already open."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "fraud_type": {"type": "STRING", "enum": FRAUD_TYPES},
            "amount": {"type": "INTEGER", "nullable": True},
            "app": {"type": "STRING", "nullable": True},
        },
        "required": ["fraud_type"],
    },
}

DRAFT_1930_REPORT = {
    "name": "draft_1930_report",
    "description": (
        "Produce the 1930/NCRP complaint draft for the victim to file "
        "themselves. This PREPARES a document. It does not submit anything "
        "anywhere -- no submission exists in this system."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "case_id": {"type": "STRING"},
            "victim_statement_hi": {
                "type": "STRING",
                "description": (
                    "The incident narrative in Hindi, written in Devanagari, "
                    "keeping English tech terms (KYC, OTP, bank, PhonePe, "
                    "1930) in Latin script per the script rule. Third person "
                    "factual account, 3-5 sentences, built ONLY from what the "
                    "victim said. Do not add detail they did not give. Never "
                    "include an OTP, PIN or password even if they said one."
                ),
            },
        },
        "required": ["case_id", "victim_statement_hi"],
    },
}

# Order is load-bearing: the orchestrator walks this list.
RESCUE_TOOLS = [
    CLASSIFY_FRAUD,
    EXTRACT_ENTITIES,
    CREATE_CASE,
    DRAFT_1930_REPORT,
]

TOOLS_BY_NAME = {t["name"]: t for t in RESCUE_TOOLS}
