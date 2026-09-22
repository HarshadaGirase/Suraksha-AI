# SurakshaAI — Build Plan (revised)

Spec of record: `CLAUDE.MD`. This file records the **corrections** to that spec and the
**day-by-day order**. Where the two disagree, this file wins until CLAUDE.MD is patched.



---

## PART 1 — SPEC CORRECTIONS (apply before writing code)

### C1. The bleep, as specified, cannot work. (blocking)

CLAUDE.MD §7: *"gain-mute triggered by STT word timestamps matching digits/OTP keyterms."*

Causality: victim speaks digit → audio leaves the client → AssemblyAI → partial returns
(~300ms) → client mutes. **The digit is already gone.** A word timestamp describes the
past. You cannot un-send audio. §18 lists "bleep" under *NOT mocks* — this is the
weakest claim in the document and the first thing a judge who knows streaming will ask.

**Fix — mute predictively, not reactively:**

1. Guard ARMS when threat state hits `critical` (scammer has demanded an OTP). This is
   allowed to be slow — it happens during the scammer's turn.
2. Once armed, the **victim's outbound channel is severed** the instant local VAD detects
   the victim speaking. Zero latency: no STT round trip, no per-word decision.
3. You mute **the channel, not the digit**. You never need to know which word is a digit.
4. STT word timestamps are then used for **evidence and display only** (rendering `••••••`
   in the transcript, proving in the forensic report that digits were spoken while muted).

Reframe the claim: *"once OTP harvesting is detected, we sever the victim's audio channel
to the scammer"* — buildable, honest, and stronger than per-word bleeping.

**Also:** this build has **no outbound leg at all** (mic → our own backend). "Scammer never
hears it" is a claim about a production telephony path that does not exist here. Put it on
the honesty list as an entry-point substitution — exactly as §18 already does, honestly,
for the phone line.

### C2. The Golden Clock inflates a number reality already beats. (blocking)

5 Gemini Flash calls + 1 pgvector query + 2 PDF renders ≈ **15–30 seconds**. Not 3:40.
The mockup animates a fake clock to `T+3:40` over 4.4 real seconds — padding the product
to look *slower*.

**Fix: show real wall-clock elapsed, uncapped. Delete the T+3:40 target.**
"Documents ready in 28 seconds vs 4–6 hours manual" is a far better line, and it is true.

### C3. Build order contradicts the stated hero. (blocking)

§1: rescue is *"the hero and the anti-clone differentiator."*
§19: builds guard (M2) **before** rescue (M3).

On an 8-day clock, whatever is built last gets cut. Current order cuts the differentiator
and ships the commodity half.

**Fix: build Act 2 (Rescue) first.** It also has no impossible-physics claim and is fully
demoable with nothing but a mic. Act 1 becomes the sandbox showcase, built second.

### C4. Transcript persistence contradicts the privacy claim. (blocking)

§10.1: *"The call NEVER collects PII."*
§12: `transcript JSONB` stores the entire panic call verbatim — the victim's narrative,
account numbers if spoken, and the OTP itself if they blurt it before the guardrail fires.

**Fix:** redact runs of ≥4 consecutive digits at the WS#1 boundary, **before** anything is
persisted. Then the claim in the pitch is actually true.

### C5. Gate 0 is resolved — and it's good news.

Verified against AssemblyAI docs:

- **Hindi IS supported on streaming**, via `speech_model=universal-3-5-pro`
  (18 languages; `universal-streaming-english` and the older
  `universal-streaming-multilingual` do **not** include Hindi — do not use them).
- **Hinglish code-switching is native** — mid-utterance language switches are handled in a
  single pass, no language-pair parameter, no routing step.
- **Word timestamps exist in streaming.** `Turn` messages carry `words[]` with
  `text, start, end, confidence, word_is_final`; timings in **milliseconds**.
- **`keyterms_prompt`**: up to 100 terms, ≤50 chars each, and **updatable mid-session** via
  `UpdateConfiguration` with no reconnect — use this to arm guard vocabulary dynamically.
- Do **not** set `language_code` — it is for monolingual sessions and will break
  code-switching.

**Gate 0 therefore shrinks to two unknowns, both stop-the-line (see D0).**

### C6. "No fallbacks" applied to unverified dependencies is a contradiction.

The no-alternatives rule is good discipline *after* verification, not before. Fallback
decisions are permitted **only at Gate 0**; after that the stack locks.

### C7. Guard rules must be written against observed STT output — never against §15.

Whether Hindi returns in **Devanagari or romanized Latin** decides whether your keyterms
are `"ओटीपी"` or `"OTP batao"`. You cannot write a single guard rule until you have seen
real output. Capture it at D0 and treat that capture as the fixture.

### C8. PDF/Devanagari decision moves to Day 0, not M3.

WeasyPrint needs system libs (cairo/pango) and an embedded **Noto Sans Devanagari** with
correct conjunct shaping; reportlab's Devanagari shaping is worse. A dossier that renders
as tofu boxes on Day 7 is unrecoverable.

**Decide now: WeasyPrint in Docker with the font bundled. Render one Hindi PDF on Day 0.**

### C9. Deploy moves from last to Day 4.

Render free tier idles down after ~15 min (~50s cold start). A judge opens the link, the
WebSocket dies, the project reads as broken. Required: deploy early, a visible
*"waking backend…"* state instead of a dead socket, an uptime pinger, and **WSS not ws://**
(mixed content is blocked on an HTTPS Vercel page).

### C10. Gemini free tier will rate-limit mid-demo.

5 sequential calls per run × rehearsals. One 429 during the pitch ends it. Needs: retry
with backoff, a second API key, and visible graceful degradation rather than a hang.

### C11. Missing from the spec entirely.

WS#1 reconnection, AssemblyAI mid-call drop, and any UI error surface beyond
`{"type":"error"}`. Conference wifi will find all three. Add a visible connection state.

---

## PART 2 — MOCKUP BUGS (fix during the React port)

The mockup's design is strong and the MOCK DATA MANIFEST comment block is excellent
practice — **carry it into React as per-component comments.** These are the defects:

| # | Issue | Why it matters |
|---|---|---|
| 1 | `toggleMic` stores AudioContext in local `const ctx`; `stopMic` closes `window._ac`, which is never assigned | **AudioContext is never closed.** Browsers cap ~6 per page — the 6th mic test silently fails |
| 2 | `fullDemo` has **no reset** | Button says "RE-RUN"; second run appends duplicate transcript bubbles, re-shows evidence, restarts the clock. Will break on a live re-run |
| 3 | `animFake` sets `window._fakeIv` but never clears the previous interval | Intervals stack across runs |
| 4 | Dead no-op: `$('micBtn').addEventListener('click',()=>{...{}},true)` | Delete |
| 5 | ~12 hardcoded `setTimeout`s drive the whole demo | In React this must be an event-driven state machine off WS#1, or the UI desyncs from the real pipeline |
| 6 | **Violates its own BLANK-STATE POLICY**: `98.7%`, `₹40000`, `PhonePe`, `99.6/99.1/98.4%` are hardcoded in static HTML | §16 says never pre-fill. Must render from `tool.result` / `evidence.update` |
| 7 | `.ic` is both the infra-card class and the empty-state icon class | CSS collision; `.empty .ic` wins on specificity but it's fragile |
| 8 | Tabs/buttons are `<div>`/`<span>` + `onclick` | No keyboard access, no roles. Cheap to fix when porting |
| 9 | `downloadDocs` builds a hardcoded ₹40,000 blob | Must become `GET /api/case/{id}/docs` |
| 10 | `B(id,cls,who,txt)` — first param unused | Cleanup |

---

## PART 3 — DAY BY DAY

**Governing rule: the app must be demoable at the end of every single day.**

### D0 — Sep 22 (today, ~2h) · GATE 0 · stop-the-line
Two unknowns, both of which invalidate the build if they fail:

1. **Streaming capture.** Real session, `speech_model=universal-3-5-pro`, speak the §15 KYC
   script. Record raw JSON to `fixtures/stt_hinglish.jsonl`. Answer:
   - Devanagari or romanized? → decides every guard keyterm (C7)
   - Do `words[]` with `start`/`end` arrive on **partials** (`end_of_turn:false`) or only on
     final turns? → decides whether live `••••••` rendering is possible at all
   - Measured latency to first partial → replaces the guessed 280ms
2. **Devanagari PDF.** WeasyPrint in Docker, Noto Sans Devanagari bundled, render one page
   of the §13 Hindi victim statement. Conjuncts correct, no tofu. (C8)

*That fixture file becomes the test input for the entire rest of the build.*

### D1 — Skeleton, blank → live
Docker Postgres+pgvector · FastAPI `/ws/audio` · React mic → AudioWorklet → 16kHz PCM16 →
WS#1 → AssemblyAI → **partials rendering in the transcript panel.** UI shell with all
blank states. Nothing else.

### D2 — Act 2 Rescue core ← *the hero, built first* (C3)
5 Gemini tools, sequential, strict JSON schemas · `tool.call`/`tool.result` events ·
case card fills from `case.update` · **real uncapped clock** (C2) · digit redaction before
persist (C4).

### D3 — RAG + documents
pgvector corpus (~60 chunks) · `draft_freeze_letter` with a genuine retrieved citation ·
WeasyPrint PDFs · `GET /api/case/{id}/docs` zip · **download works end to end.**
→ At this point Act 2 is complete and demoable on its own.

### D4 — DEPLOY PUBLIC MODE ← *moved up from M6* (C9)
Vercel + Render + Neon · WSS · cold-start UX · 2-user concurrency test.
Then: edge-tts endpoint, cached hero MP3s, half-duplex (§7.2).

### D5 — Act 1 Guardian
Sandbox MP3 segment injection through the **same PCM path** as mic (§7.1 — this part of the
spec is right and worth protecting) · guard rules written from the D0 fixture, not from §15 ·
**predictive channel mute** (C1) · forensic report.

### D6 — Live mic mode, stats, resilience
Real AnalyserNode spectrum · latency logging → `stat.update` · WS reconnect + visible
connection state (C11) · Gemini 429 handling (C10).

### D7 — Sep 29 · Polish + rehearse
Idle states · `[SIM]` chips · delete `#devStrip` · README (architecture, two-mode run,


### D8 — Sep 30 · Buffer, submit early
Submit with hours to spare, not minutes.

---

## PART 4 — WHAT THE SPEC GETS RIGHT (do not change these)

- Scope discipline and the explicit OUT OF SCOPE list — unusually good, protect it.
- The no-auto-submission stance. Legally and ethically correct, and §10.1's
  "[FILL AT FILING]" split turns a limitation into a genuine privacy feature.
- Sandbox audio as **scripted input through the real pipeline**, never speaker re-capture (§7.1).
- Client-side downsampling to 16kHz before the socket (§7.3).
- Half-duplex echo protection (§7.2).
- Exactly 2 WebSockets, keys only in FastAPI.
- The honesty list existing at all (§18) — it just needs C1 added to it.
