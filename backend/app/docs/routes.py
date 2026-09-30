"""Document download (CLAUDE.MD §16).

GET /api/case/{id}/docs is the ONLY victim action in Act 2. There is no submit
route here and there never will be: §2 makes filing the victim's own act, and
the absence of an endpoint is the enforcement.
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Response

from app.db import cases as repo
from app.docs.render import PdfUnavailable, render_pdf

log = logging.getLogger(__name__)
router = APIRouter()


def _load_draft(row: dict) -> dict:
    draft = row.get("draft")
    if isinstance(draft, str):
        return json.loads(draft)
    return draft or {}


@router.get("/api/case/{case_id}/docs")
async def download_docs(case_id: str, format: str = "pdf") -> Response:
    """The 1930 complaint draft, as a PDF or as JSON.

    JSON is offered alongside the PDF so the output is inspectable rather than
    something you have to take on trust — every field can be traced back to a
    tool_events row.
    """
    row = await repo.get_case(case_id)
    if row is None:
        raise HTTPException(status_code=404, detail="case not found")

    draft = _load_draft(row)
    if not draft:
        raise HTTPException(
            status_code=409,
            detail="draft not ready — the complaint has not been prepared yet",
        )

    created = row.get("created_at")
    if format == "json":
        return Response(
            content=json.dumps(draft, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
        )

    try:
        pdf = render_pdf(draft, created_at=created if isinstance(created, datetime) else None)
    except PdfUnavailable as exc:
        # The host is missing cairo/pango. Point at the format that still
        # works rather than just failing — the victim's facts are all there.
        log.error("PDF unavailable on this host: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="PDF rendering is unavailable on this host. "
                   f"The draft is still available at "
                   f"/api/case/{case_id}/docs?format=json",
        ) from exc
    except Exception as exc:
        log.exception("PDF render failed for %s", case_id)
        raise HTTPException(status_code=500, detail=f"render failed: {exc}") from exc

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            # "draft" in the filename on purpose: the file gets forwarded and
            # re-shared, and the name is the only context that travels with it.
            "Content-Disposition": (
                f'attachment; filename="1930-complaint-draft-{case_id}.pdf"'
            )
        },
    )
