"""Case and tool-event persistence (CLAUDE.MD §12).

Every write in this module passes its free text through app.redact first. That
is not a convenience — §10.1 claims the call never collects PII, and this is the
only place that claim is made true. Bypassing these functions to write a raw
transcript would silently falsify the pitch.

Nothing here can set status='submitted'. The schema's CHECK constraint refuses
it and §2 forbids it; both exist so that neither a bug nor a well-meaning
refactor can create a "filed" case.
"""

import json
import logging
import random
import string
from datetime import datetime, timezone
from typing import Any

from app.db.pool import get_pool
from app.redact import redact_json

log = logging.getLogger(__name__)

_ID_ALPHABET = string.digits


def new_case_id() -> str:
    """Case reference shown to the victim, e.g. 'GH-4821'.

    GH = Golden Hour. Four digits is enough for a demo and short enough to read
    aloud over the phone, which is the point — the victim may be quoting this
    back to a 1930 operator.
    """
    return "GH-" + "".join(random.choices(_ID_ALPHABET, k=4))


async def create_case(
    *,
    case_id: str,
    act: str | None = None,
    scenario: str | None = None,
    fraud_type: str | None = None,
    confidence: float | None = None,
    amount: int | None = None,
    app: str | None = None,
    utr: str | None = None,
    when_ago: str | None = None,
    district: str | None = None,
    suspect_number: str | None = None,
    language_code: str | None = None,
    language_confidence: float | None = None,
    transcript: list[dict[str, Any]] | None = None,
) -> str | None:
    """Insert a case. Returns the id, or None if there is no database.

    A missing database degrades to an in-memory demo rather than an error: the
    case card still fills from WS#1 events, only the record is not kept.
    """
    pool = get_pool()
    if pool is None:
        return None

    safe_transcript = redact_json(transcript or [])
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cases (
                    id, act, scenario, fraud_type, confidence,
                    amount, app, utr, when_ago, district, suspect_number,
                    language_code, language_confidence, transcript
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                )
                """,
                case_id, act, scenario, fraud_type, confidence,
                amount, app, utr, when_ago, district, suspect_number,
                language_code, language_confidence, json.dumps(safe_transcript),
            )
        return case_id
    except Exception as exc:
        log.warning("create_case failed: %s", exc)
        return None


async def update_case(case_id: str, **fields: Any) -> None:
    """Patch a case with whatever the agent has learned since.

    Entities arrive across several turns — the amount in one sentence, the app
    two questions later — so this is called repeatedly. Only the columns passed
    are touched; a field the victim has not mentioned stays NULL rather than
    being overwritten with a guess (§10.1).
    """
    pool = get_pool()
    if pool is None or not fields:
        return

    allowed = {
        "act", "scenario", "fraud_type", "confidence", "amount", "app", "utr",
        "when_ago", "district", "suspect_number", "language_code",
        "language_confidence", "status",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    for js in ("transcript", "draft"):
        if js in fields and fields[js] is not None:
            updates[js] = json.dumps(redact_json(fields[js]), ensure_ascii=False)
    if not updates:
        return

    cols = ", ".join(f"{k} = ${i}" for i, k in enumerate(updates, start=2))
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                f"UPDATE cases SET {cols} WHERE id = $1",
                case_id, *updates.values(),
            )
    except Exception as exc:
        log.warning("update_case failed: %s", exc)


async def get_case(case_id: str) -> dict[str, Any] | None:
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM cases WHERE id = $1", case_id)
        return dict(row) if row else None
    except Exception as exc:
        log.warning("get_case failed: %s", exc)
        return None


async def log_tool_event(
    *,
    case_id: str | None,
    name: str,
    args: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    ms: int | None = None,
) -> None:
    """Record one tool call. Feeds the tool panel and the forensic record.

    args and result are redacted too, not just the transcript: an extracted
    entity blob is exactly where a stray digit run would otherwise land.
    """
    pool = get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tool_events (case_id, name, args, result, ms)
                VALUES ($1, $2, $3, $4, $5)
                """,
                case_id,
                name,
                json.dumps(redact_json(args or {})),
                json.dumps(redact_json(result or {})),
                ms,
            )
    except Exception as exc:
        log.warning("log_tool_event failed: %s", exc)


async def mark_documents_ready(case_id: str) -> None:
    """The terminal state. There is no state after this one (§12)."""
    await update_case(case_id, status="documents_ready")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
