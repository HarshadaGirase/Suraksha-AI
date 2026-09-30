# SurakshaAI — Build Plan (rev. 2026-09-30)

Spec of record: `CLAUDE.MD`. The corrections that used to live here have now
been folded into that file (see its §21 change log), so this file is just the
build order, the verification bar, and the open risks.

---

## Scope, in one box

> **ACT 1** — intercept: detect → sever the victim's channel → counter-interrogate
> → terminate. Output: **Forensic Incident Record**.
>
> **ACT 2** — rescue: victim talks → classify → extract → **1930 / NCRP complaint
> draft**. Output: **one PDF + JSON**.

Four Gemini tools. One document. One database. No vector search.

**Cut deliberately:** bank freeze letter · RAG/pgvector · sandbox file upload
(deferred) · Tamil/Telugu/Bengali/etc (not on any streaming model).

---

## The three things that must stay true

1. **Never submit.** No auto-filing, no bank contact, no "submitted" state
   anywhere in code, schema or copy. The product prepares; the victim files.
2. **Never ask for an OTP.** An AI that asks for a code is indistinguishable
   from the scam it is fighting. The guardrail fires before any tool call.
3. **Never persist a digit run.** `redact.py` runs before every write.

---

## Batches

### GATE 0 — stop-the-line, not yet run

Stream a §15 Hinglish clip through `universal-3-6-pro`; dump every raw message
to `fixtures/stt_<clip>.jsonl`. Three answers:

1. **Devanagari or romanised Latin?** Decides whether guard keyterms are
   `"ओटीपी"` or `"OTP batao"`. **No guard rule can be written before this.**
2. **Do `words[]` arrive on partials (`end_of_turn:false`) or only on finals?**
   Decides whether live `••••••` rendering is possible at all.
3. **Measured latency to first partial** — replaces the guessed 280ms.

Needs `ASSEMBLYAI_API_KEY` in `.env`. Costs about ₹1.

### A — Foundation

Docker Postgres · `cases` + `tool_events` per §12 · async pool · every write
through `redact.py` · `/api/health` reports DB reachability, not just config.

### B — Act 2 Rescue (the hero)

Gemini Flash with strict JSON function-calling · the 4 tools · rescue
orchestrator firing off victim `transcript.final` · OTP guardrail before any
tool · real uncapped clock starting at `create_case` · case card and tool panel
filling from events.

**Done when:** speak Hinglish into the mic, watch the case card fill, with no
hardcoded value anywhere.

### C — The document

WeasyPrint with Noto Sans Devanagari bundled · §10.1 field split · §11 rights
block · `GET /api/case/{id}/docs`.

**Render one Hindi page as the first act of this batch.** Conjuncts correct, no
tofu. A dossier that renders as boxes discovered late is unrecoverable.

### D — Act 1 Guardian

Sandbox MP3 injection through the same PCM path (§7.2) · guard rules written
from the Gate 0 fixture, never from §15 · the `1600xx` check · channel cut on
local VAD (§7.1) · forensic record.

### E — Voice

edge-tts endpoint · 4 cached hero MP3s · half-duplex (§7.3).

### F — Deploy PUBLIC MODE

Vercel + Render + Neon · **Deployment Protection OFF** · `wss://` · cold-start
UX · 2-user concurrency test.

### G — Polish

`[SIM]` chips · latency stats wired to all four cards · README · honesty list.

---

## Open risks

| Risk | Mitigation |
|---|---|
| **Gate 0 has never run.** Guard keyterms are unknowable until it does. | Run it the moment the key is in `.env`. Act 2 (batches A–C) does not depend on it, so the build is not blocked. |
| **Render free tier idles down** (~50s cold start). A judge opens the link and the socket looks dead. | Deploy at F with a visible "waking backend…" state and an uptime pinger. Never a bare failed socket. |
| **Gemini free tier will rate-limit** mid-demo. 4 calls per run × rehearsals. | Retry with backoff, a second API key, visible graceful degradation rather than a hang. |
| **Devanagari PDF shaping.** WeasyPrint needs the font bundled and correct conjunct shaping. | First act of batch C, not the last. |
| **RBI paragraph numbers are unverified.** The PDF is CAPTCHA-blocked; circulating numbers are from the March draft. | §11 prints instrument + date and **no paragraph number**. A gap beats a wrong citation on a document handed to an official. |
| **WS#1 reconnection / mid-call STT drop.** Conference wifi finds both. | Capped-backoff reconnect and a visible connection state — already built. |

---

## Verification bar

No batch is called done because code exists. Each one states what was run and
what came back:

- **Gate 0** — the fixture file exists and contains recognisable Hinglish; the
  three questions are answered in writing.
- **A** — `docker compose up`, `\dt` shows both tables, `/api/health` returns
  200 with `db: online`.
- **B** — a real spoken sentence produces a real `case.update` with no hardcoded
  values.
- **C** — the downloaded PDF opens, Hindi renders without tofu, and every
  `[FILL AT FILING]` field is blank.
- **D** — the channel measurably goes silent before the first digit's timestamp.
- **F** — two browsers, two concurrent sessions, from a link with no login wall.

---

## Mockup defects — carried into the React port

These were in the original HTML and must not come back:

| # | Issue |
|---|---|
| 1 | `toggleMic` stored the AudioContext in a local `const`; `stopMic` closed a different one → contexts leaked, browsers cap ~6 per page. **Fixed in `useMic.js`.** |
| 2 | `fullDemo` had no reset → a second run appended duplicate bubbles and restarted the clock. |
| 3 | `animFake` never cleared the previous interval → intervals stacked. |
| 4 | ~12 hardcoded `setTimeout`s drove the demo → must be an event-driven state machine off WS#1. |
| 5 | **Violated its own blank-state policy**: `98.7%`, `₹40000`, `PhonePe` hardcoded in static HTML. |
| 6 | Tabs/buttons were `<div>` + `onclick` → no keyboard access. **Fixed: real `<button>`s.** |
| 7 | `downloadDocs` built a hardcoded ₹40,000 blob → must become `GET /api/case/{id}/docs`. |

---

## What the original spec got right (do not change)

- The explicit OUT OF SCOPE list — unusually good discipline, protect it.
- The no-auto-submission stance, and §10.1's `[FILL AT FILING]` split, which
  turns a limitation into a genuine privacy feature.
- Sandbox audio as **scripted input through the real pipeline**, never speaker
  re-capture (§7.2).
- Client-side downsampling to 16kHz before the socket (§7.4).
- Half-duplex echo protection (§7.3).
- Exactly 2 WebSockets, keys only in FastAPI.
- The honesty list existing at all (§18).
