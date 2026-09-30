"""1930 / NCRP complaint draft rendering (CLAUDE.MD §3, §10.1, §11).

Fonts are bundled in app/docs/fonts and declared with @font-face rather than
relied on from the host. The dev machine happens to have Noto Sans Devanagari
installed; Render's Python image does not, and a dossier that renders as tofu
boxes on the deployed link is worse than no dossier at all (PLAN.md batch C).

Nothing in this module invents a value. Structured fields come from the case
record -- i.e. from something the victim actually said -- and a field that was
never spoken renders as a visible blank, not as a guess (§10.1).
"""

import html
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

FONT_DIR = Path(__file__).parent / "fonts"

# §11. Static, hand-verified against CLAUDE.MD §2. Not model output and not
# retrieval -- there is no vector search in this build. No paragraph numbers:
# RBI's PDF is CAPTCHA-blocked and the numbers in circulation come from
# analyses of the March 2026 draft, not the final June text. A missing
# paragraph number is a gap; a wrong one on a document handed to an official
# is a lie.
RIGHTS = [
    "अपने bank को आज ही लिखित में बताइए। Zero liability इस पर depend करती है कि "
    "आपने bank को कब बताया — अभी 3 working days, और 1 जनवरी 2027 से 5 calendar days।",
    "Bank को साबित करना होगा कि गलती आपकी थी — आपको नहीं।",
    "धोखे में आकर OTP बताना भी 1 जनवरी 2027 से cover होता है।",
]
RIGHTS_SOURCE = (
    "RBI (Commercial Banks – Responsible Business Conduct) Directions, 2025 · "
    "Third Amendment Directions, 2026 (24 Jun 2026, in force 1 Jan 2027)"
)

HOW_TO_FILE = [
    "1930 पर call कीजिए, या cybercrime.gov.in पर जाइए।",
    "ऊपर भरे हुए fields पढ़ कर बता दीजिए।",
    "Bank statement और payment app की receipt साथ रखिए।",
    "File करने के बाद जो 14-digit acknowledgement number SMS पर आएगा, "
    "वो ऊपर वाले box में लिख लीजिए।",
]

_CSS = """
@font-face {
  font-family: 'NotoDeva';
  src: url('file://%(regular)s') format('truetype');
  font-weight: normal;
}
@font-face {
  font-family: 'NotoDeva';
  src: url('file://%(bold)s') format('truetype');
  font-weight: bold;
}
@page { size: A4; margin: 16mm 14mm; }
body {
  font-family: 'NotoDeva', 'DejaVu Sans', sans-serif;
  font-size: 10pt; color: #111; line-height: 1.5;
}
h1 { font-size: 15pt; margin: 0 0 2mm; }
.banner {
  border: 1.2pt solid #111; padding: 3mm 4mm; margin-bottom: 5mm;
}
.notfiled {
  font-weight: bold; font-size: 10.5pt; margin-top: 1.5mm;
}
h2 {
  font-size: 9pt; letter-spacing: 0.8pt; text-transform: uppercase;
  border-bottom: 0.6pt solid #999; padding-bottom: 1mm;
  margin: 6mm 0 2mm;
}
table { width: 100%%; border-collapse: collapse; }
td { padding: 1.4mm 0; vertical-align: top; }
td.k { width: 42mm; color: #555; }
td.v { font-weight: bold; }
.blank {
  display: inline-block; min-width: 72mm;
  border-bottom: 0.6pt solid #666; height: 4.5mm;
}
.narrative {
  background: #f5f5f5; padding: 3mm 4mm; margin-top: 1mm;
}
.rights li { margin-bottom: 1.5mm; }
.src { font-size: 8pt; color: #555; margin-top: 2mm; }
.foot {
  margin-top: 7mm; border-top: 0.6pt solid #999; padding-top: 2mm;
  font-size: 8pt; color: #555;
}
.missing { color: #a00; font-weight: bold; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _row(label: str, value: Any, *, note: str = "") -> str:
    """One field. An unspoken field renders as a visible gap, never as a guess."""
    if value in (None, "", []):
        shown = f'<span class="missing">— not stated{(" — " + note) if note else ""}</span>'
    else:
        shown = _esc(value)
    return f'<tr><td class="k">{_esc(label)}</td><td class="v">{shown}</td></tr>'


def _blank_row(label: str) -> str:
    return f'<tr><td class="k">{_esc(label)}</td><td><span class="blank"></span></td></tr>'


def build_html(draft: dict[str, Any], *, created_at: datetime | None = None) -> str:
    """Render the complaint draft to HTML."""
    when = (created_at or datetime.now(timezone.utc)).astimezone()
    amount = draft.get("amount")
    amount_text = f"₹ {amount:,}" if isinstance(amount, int) else None
    confidence = draft.get("confidence")
    fraud = draft.get("fraud_type")
    fraud_text = (
        f"{fraud} ({confidence:.0%} confidence)"
        if fraud and isinstance(confidence, (int, float))
        else fraud
    )

    rights = "".join(f"<li>{_esc(r)}</li>" for r in RIGHTS)
    steps = "".join(f"<li>{_esc(s)}</li>" for s in HOW_TO_FILE)
    blanks = "".join(_blank_row(f) for f in draft.get("fill_at_filing", []))

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_CSS % {
        "regular": FONT_DIR / "NotoSansDevanagari-Regular.ttf",
        "bold": FONT_DIR / "NotoSansDevanagari-Bold.ttf",
    }}</style></head><body>

<div class="banner">
  <h1>1930 / NCRP Complaint — DRAFT</h1>
  <div>Case {_esc(draft.get("case_id"))} · prepared {when:%d %b %Y, %H:%M %Z}
       · prepared in {_esc(draft.get("elapsed", "—"))}</div>
  <div class="notfiled">यह draft है — अभी file नहीं हुआ है। आपको खुद file करना है।</div>
</div>

<h2>Category</h2>
<table>
  {_row("Category", draft.get("category"))}
  {_row("Sub-category", draft.get("sub_category"))}
  {_row("Fraud pattern", fraud_text)}
</table>

<h2>Transaction</h2>
<table>
  {_row("Amount lost", amount_text)}
  {_row("App / rail", draft.get("app"))}
  {_row("Transaction ID / UTR", draft.get("utr"),
        note="check your payment app; 1930 will ask for this")}
  {_row("When", draft.get("when_ago"))}
  {_row("District", draft.get("district"))}
</table>

<h2>Suspect</h2>
<table>
  {_row("Caller number", draft.get("suspect_number"))}
</table>

<h2>What happened</h2>
<div class="narrative">{_esc(draft.get("victim_statement_hi", ""))}</div>

<h2>To be completed by you at the time of filing</h2>
<table>{blanks}</table>

<h2>आपके rights</h2>
<ul class="rights">{rights}</ul>
<div class="src">{_esc(RIGHTS_SOURCE)}</div>

<h2>File कैसे करें</h2>
<ol class="rights">{steps}</ol>

<div class="foot">
  SurakshaAI prepared this draft from what you said on the call. It has NOT
  been submitted to 1930, to cybercrime.gov.in, or to any bank — no such
  submission exists in this system. No name, phone number, address or account
  detail was collected during the call.
</div>

</body></html>"""


class PdfUnavailable(RuntimeError):
    """WeasyPrint could not load. The draft is still available as JSON."""


def render_pdf(draft: dict[str, Any], *, created_at: datetime | None = None) -> bytes:
    """Render the draft to PDF.

    WeasyPrint is imported HERE, not at module scope, on purpose. It needs
    cairo/pango/harfbuzz as system libraries rather than pip wheels, and a host
    without them raises on import. At module scope that would propagate up
    through app.main and the entire backend would fail to boot -- the whole
    product dead because one document format is unavailable. Deferred, a
    missing system library costs the PDF and nothing else: the JSON draft, both
    acts and the live pipeline all keep working.
    """
    try:
        from weasyprint import HTML
    except Exception as exc:  # ImportError, or OSError from a missing .so
        log.error("WeasyPrint unavailable — PDF disabled: %s", exc)
        raise PdfUnavailable(str(exc)) from exc

    return HTML(string=build_html(draft, created_at=created_at)).write_pdf()
