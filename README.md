# SurakshaAI

**A real-time voice agent that intercepts Hinglish scam calls, and — when the
money has already gone — turns a panicking victim's speech into a filled-in
1930 cybercrime complaint draft in under a minute.**

Built for the **AssemblyAI Voice Agent Hackathon**.

---

## The problem

Someone calls and says they are from your bank. Your KYC has expired. Your
account will be blocked in two hours. Then they ask for the OTP that just
arrived on your phone. People give it, and the money is gone in seconds.

Two things make this harder than it looks:

- **The calls are in Hinglish** — Hindi and English mixed inside the same
  sentence — which most voice tooling handles badly.
- **Stolen money moves through rented mule accounts within hours.** India's
  national cyber-fraud helpline is **1930**, and reporting speed decides
  recovery. But a victim who has just been robbed must fill in a long form,
  including a transaction reference they have never heard of, while still
  panicking.

SurakshaAI covers both halves.

| | Act 1 — Guardian | Act 2 — Rescue *(the hero)* |
|---|---|---|
| **When** | During the call | After the money has gone |
| **Does** | Detects OTP harvesting, **severs the victim's outbound audio channel**, counter-interrogates the caller, terminates | Victim speaks Hinglish; the agent classifies the fraud, extracts the facts, **asks aloud for anything missing**, and builds the complaint |
| **Output** | Forensic incident record | **1930 / NCRP complaint draft (PDF)** |

---

## The hard rules

These are enforced in code, not just intended.

1. **The AI never files anything.** It never calls 1930, never submits to
   cybercrime.gov.in, never contacts a bank. No public API exists, the portal
   requires the victim's own credentials, and we never take credentials. The
   product prepares a draft; the victim files it. There is **no submit
   endpoint**, and `status` is constrained by the database to
   `drafted | documents_ready` — a refactor cannot create a "filed" case.
2. **The agent never accepts an OTP.** A cue word plus a digit run triggers a
   refusal *before the model sees the turn*. An AI that asks for a code is
   indistinguishable from the scam it is fighting.
3. **No digit run is ever persisted.** Runs of four or more digits are masked
   before anything reaches the database. Helpline numbers (`1930`, `112`,
   `155260`) are allowlisted and amounts are preserved, so the complaint can
   still state what was lost.
4. **No PII is collected on the call.** Name, phone, address and account
   details print as blank fields on the draft, to be filled at filing time.

---

## The two findings that shaped the build

**1. Per-word bleeping is physically impossible.**

The original design was to watch STT word timestamps and mute the exact word
containing a digit. Gate 0 measured **1042–1125 ms** from first audio chunk to
first partial. By the time the transcript says a digit was spoken, that audio
left the machine a full second ago. A timestamp describes the past.

So the guard **arms** during the *caller's* turn — where being slow is free —
and the victim's **entire outbound channel** is severed by local VAD in the
AudioWorklet, on the audio thread, in the same render quantum. The frames are
never handed to `postMessage`, so nothing reaches the socket. We mute the
**channel**, not the word, and never need to know which word is a digit.

Word timestamps are still used — for evidence and for rendering `••••••` — but
never as the trigger.

**2. Guard rules had to be written from real STT output, not from the script.**

The scenario scripts are pure Devanagari. Universal-3.6 Pro returns
**code-switched** text — Hindi in Devanagari, English technical terms left in
Latin:

```
मैडम जी, मैं SBI हेड ओफिस से बोल रहा हूँ।
आपका KYC एक्स्पायर हो गया है।
दो घंटे में अकाउंट ब्लॉक हो जाएगा, एक OTP आने वाला है, वो मुझे बोल दीजिए अभी.
```

So the OTP keyterm is the Latin `OTP`, not `ओटीपी`. Every rule written from
the script would have matched **nothing**. They are written against
`fixtures/stt_kyc_scammer.jsonl` instead.

---

## The strongest signal needs no AI

RBI requires regulated entities to make transactional calls from the **`1600xx`
numbering series** (circular of 17 Jan 2025, compliance due 31 Mar 2025).

> A caller claiming to be SBI while calling from an ordinary 10-digit mobile
> **cannot lawfully be SBI.**

That is an `if` statement, confidence 1.0, no model involved — and it is scored
high enough to trip `critical` on its own. It also gives the counter-interrogation
something a scammer cannot talk his way out of: an employee ID can be invented
on the spot, a `1600xx` line cannot.

---

## Architecture

```
 [ Browser ]                                  [ FastAPI ]              [ AssemblyAI ]

 getUserMedia 44.1/48kHz
        ↓
 pcm-worklet.js  (audio thread)
   · downsample → 16kHz PCM16 mono
   · local VAD → CHANNEL CUT ←──── armed when threat = critical
   · 100ms chunks
        ↓ binary over WS#1
 useSurakshaSocket ───────────────────→  /ws/audio  ──────────────→  universal-3-6-pro
   · reducer over 14 event types          · CallSession routes           (WS#2, SDK)
   · capped-backoff reconnect               by act
   · BLANK until an event arrives          ├── Guardian  (Act 1)
        ↑                                  │     rules · arm · forensic
        └──────────── §9 events ───────────┤
                                           └── RescueAgent (Act 2)
 useTts                                          Gemini Flash · 4 tools
   · queues clips, holds the mic                 ↓
   · releases 300ms after playback           PostgreSQL ← redact.py
                                                 ↓
                                             WeasyPrint → 1930 draft PDF
```

**Exactly two WebSockets.** WS#1 is ours (browser ↔ FastAPI); WS#2 is
SDK-managed (FastAPI ↔ AssemblyAI). Everything else is plain HTTP. **API keys
live only in FastAPI, never in React.**

### Why the backend cannot be serverless

Vercel's serverless functions do not hold a WebSocket open, so WS#1 dies. The
frontend is on Vercel; the backend runs as a normal long-lived process on
Render.

---

## Stack

| Layer | Choice |
|---|---|
| Frontend | React 18 · Vite 6 · Tailwind v4 |
| Backend | Python 3.11 · FastAPI |
| STT | AssemblyAI Streaming `universal-3-6-pro` |
| LLM | Google Gemini Flash, JSON function-calling |
| DB | PostgreSQL 16 (Docker) |
| TTS | edge-tts, MD5 disk cache |
| PDF | WeasyPrint + bundled Noto Sans Devanagari |

### Language reach — stated honestly

`universal-3-6-pro` covers 32 languages with native code-switching. Of Indian
languages that is **Hindi, Marathi and Urdu**, so Hinglish, Marathi-English and
Urdu-English all work live, mid-sentence, in a single pass.

**Tamil, Telugu, Bengali, Kannada, Malayalam, Gujarati, Punjabi and Assamese are
not available on any streaming model.** They are out of scope for this build and
are not claimed.

---

## Running it

### 1. Database

```bash
docker compose -f infra/docker-compose.yml up -d
```

Postgres listens on **5433**, not 5432 — a system Postgres on the default port
collides silently and you end up connected to the wrong database with no schema.

### 2. Environment

```bash
cp .env.example .env
```

Fill in `ASSEMBLYAI_API_KEY` and `GEMINI_API_KEY`.

> **`STT_ENABLED` defaults to `false`, on purpose.** With a key present, every
> browser that opens `/ws/audio` would start a **billed** AssemblyAI stream, and
> a forgotten tab burns credit with nothing on screen. Set it to `true` only for
> a live test, then set it back. `STT_MAX_SESSION_SECONDS` (180) is the second
> net.

### 3. Backend

```bash
cd backend
uv venv && uv pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
curl localhost:8000/api/health
# {"status":"ok","services":{"stt":"disabled","gemini":"configured","database":"online"}}
```

`stt: disabled` means the key is present but held back. `stt: missing_key` means
there is no key. The database reports **real reachability**, not just whether
the env var is set.

### 4. Frontend

```bash
cd frontend
npm install && npm run dev      # http://localhost:5173
```

Vite proxies `/ws` and `/api` to `localhost:8000`, so the browser sees one origin.

---

## Testing without spending credit

Both acts can be exercised end to end with **zero AssemblyAI usage**. This is
not a convenience — it is what let the whole product be built against a $50
balance.

```bash
cd backend

# Act 2: scripted victim turns straight into the orchestrator, standing in for
# transcript.final events. Real Gemini, real Postgres, no streaming.
.venv/bin/python ../scripts/test_rescue.py

# Act 1: replays the Gate 0 fixture — the transcripts AssemblyAI actually
# returned — through the guard. No network at all.
.venv/bin/python ../scripts/test_guard.py
```

`test_guard.py` also asserts two controls: a `1600xx` caller must **not** trip
the illegal-series rule, and a call where the cut never happened must record the
leak rather than claim a clean intercept.

### Gate 0 (spends a few seconds of credit)

```bash
# set STT_ENABLED=true first
.venv/bin/python ../scripts/gate0_stream.py kyc_scammer
```

Writes every raw message to `fixtures/`. That file is the fixture everything
else is tested against, so these questions are never re-asked at a cost.

---

## Deployment

### Backend → Render

Dashboard → **New → Blueprint** → point at this repo. `render.yaml` is already
configured. Set in the dashboard: `ASSEMBLYAI_API_KEY`, `GEMINI_API_KEY`,
`DATABASE_URL` (Neon or Supabase), `ALLOWED_ORIGINS`.

Free tier idles down after ~15 min and takes ~50s to wake. The frontend shows
**"WAKING BACKEND… (up to 50s on free tier)"** rather than a dead socket,
because a judge who opens a cold link and sees a failing connection reads the
whole project as broken.

### Frontend → Vercel

Root Directory **`frontend`**. Set `VITE_WS_URL` to
`wss://<your-app>.onrender.com/ws/audio`.

> **Two things that will silently break a submission:**
>
> 1. **Deployment Protection must be OFF** (Settings → Deployment Protection →
>    Vercel Authentication → Disabled). Otherwise the link redirects to a Vercel
>    login and nobody can open it.
> 2. **`VITE_WS_URL` must be `wss://`, not `ws://`.** An HTTPS page cannot open
>    an insecure socket; the browser blocks it as mixed content with no useful
>    error.
>
> Share the **production domain**, not a `git-<branch>-…` preview URL.

Pushes to `main` redeploy automatically.

---

## What is real, and what is not

Stated plainly, because the difference is the point.

**Genuinely simulated:**

- **1930 auto-filing does not exist.** No public API; the portal needs the
  victim's own credentials. The product deliberately prepares a draft for manual
  filing.
- **The channel cut has no outbound leg in this build.** Audio goes mic →
  our backend. "The scammer never hears it" describes the production telephony
  path — an entry-point substitution, not a fake.
- **A browser mic instead of a phone line.** In production an Exotel/Twilio leg
  streams into the same FastAPI. Only the entry point differs.

**Not mocks — say this confidently:**

- The STT pipeline, the guard logic and the channel cut
- The Gemini tool loop and every extracted field
- Digit redaction and the OTP refusal
- Document generation and the download flow
- Sandbox scenario audio is **scripted input routed through the real pipeline**,
  never speaker re-capture

---

## Repository

```
backend/app/
  agents/      rescue orchestrator · Gemini client · prompts · clock
  guard/       Act 1 rules (written from the Gate 0 fixture) · Guardian
  tools/       the 4 tool schemas and their executors
  db/          pool · case + tool_event persistence (all writes redacted)
  docs/        WeasyPrint renderer · bundled Devanagari fonts · download route
  tts/         edge-tts service · cached hero lines
  ws/          WS#1 socket · CallSession · the §9 event contract
  redact.py    digit masking — the thing that makes the privacy claim true
frontend/src/
  lib/         useMic · useTts · useSurakshaSocket
  components/  Simulator · Architecture · ui
frontend/public/pcm-worklet.js   downsampling + local VAD + the cut
fixtures/      raw AssemblyAI output captured at Gate 0
scripts/       gate0 tooling · credit-free tests for both acts
infra/         docker-compose · schema
CLAUDE.MD      the spec, with a change log of every decision taken
```

---

## Status

| Batch | | |
|---|---|---|
| Gate 0 | Hinglish streaming verified | ✅ |
| A | Docker Postgres + schema + redacted persistence | ✅ |
| B | Act 2 rescue: 4 Gemini tools, orchestrator, OTP guardrail | ✅ |
| C | WeasyPrint PDF + download endpoint | ✅ |
| D | Act 1: guard rules, `1600xx` check, channel cut, forensic record | ✅ |
| E | edge-tts + cached hero lines + half-duplex | ✅ |
| F | PUBLIC MODE deploy | in progress |
| G | Sandbox injection UI, `[SIM]` chips, polish | remaining |
