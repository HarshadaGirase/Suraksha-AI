# SurakshaAI — Product Spec (rev. 2026-09-30)

Built for the AssemblyAI Voice Agent Hackathon.

This revision trims the product to two acts and one document. Removed: the bank
freeze letter, pgvector/RAG, the 60-chunk corpus, sentence-transformers, and
per-word bleeping. Full change log in §21.

---

## 1. PROJECT IDENTITY

**Name:** SurakshaAI

**One-liner:** Voice Guardian & Fraud Rescue Agent — severs the victim's audio
channel on live Hinglish OTP-harvesting calls, and after money is stolen turns a
panicking victim's speech into a filled-in 1930 complaint draft in under a minute.

**Positioning:** Prevention tools protect only the installed few. SurakshaAI
covers both halves of the lifecycle: DURING (intercept) and AFTER (rescue). The
rescue flow is the hero and the anti-clone differentiator — it owns the first
five minutes after the money leaves, which nobody has built for.

---

## 2. KEY DOMAIN FACTS (verified — do not restate from memory)

Every fact here was checked against a primary or near-primary source on
2026-09-30. Sources in §20. **No number, date or citation goes into generated
output unless it appears in this section.**

**1930** is India's national cyber-fraud helpline, run 24×7 by **I4C** (Indian
Cyber Crime Coordination Centre, MHA). **cybercrime.gov.in (NCRP)** is its web
companion. Both feed **CFCFRMS**, the system that actually coordinates with
banks, RBI and NPCI to hold fraudulent funds. Filing produces a **14-digit
acknowledgement number beginning with "3"**, sent by SMS.

**Speed decides recovery.** Stolen money is layered through rented mule accounts
within hours. CFCFRMS acts most effectively when the report lands within roughly
**four hours**. There is no "T+3:40" target — that number was invented and has
been deleted from this spec.

**RBI mandates the `1600xx` numbering series** for transactional and service
calls by regulated entities (circular *Prevention of financial frauds
perpetrated using voice calls and SMS*, 17 Jan 2025; compliance due 31 Mar
2025). `140xx` is for promotional calls. **A bank cannot lawfully call a
customer from a 10-digit mobile number.** This is a deterministic check, not a
model judgement, and it is the strongest single signal in Act 1.

**Customer liability framework — changing.**
- In force today: the framework originating in RBI/2017-18/15 (6 Jul 2017),
  since consolidated into the **RBI (Commercial Banks – Responsible Business
  Conduct) Directions, 2025**, Section D. Zero liability on third-party breach
  if the customer notifies the bank within **3 working days**; burden of proving
  customer liability lies on the bank.
- From **1 January 2027**: the **Third Amendment Directions, 2026** (issued
  24 Jun 2026) replace Section D with **Section DA**. The reporting window
  becomes **5 calendar days**, to **both the bank and NCRP/1930**. Critically it
  covers **authorised-but-fraudulent transactions — an OTP shared under
  deception** — which is exactly this product's scam, and was the gap banks used
  to reject these claims.

**Hard rule — the AI never files anything.** It never calls 1930, never submits
to NCRP, never contacts a bank. No public API exists, the portal requires the
victim's own credentials, and **we never take credentials**. The product
PREPARES a draft; the VICTIM files it. UI wording is "download", "ready to
file", "draft" — **never** "submitted", "filed", "closed".

---

## 3. THE TWO DOCUMENTS

| Document | Act | Built from | Purpose |
|---|---|---|---|
| **Forensic Incident Record** | 1 | guard events + call transcript | Proof of an intercepted attack ("₹0 LOST"). Kept as a record; reportable as an attempt. |
| **1930 / NCRP Complaint Draft** | 2 | `draft_1930_report` over the case record | The victim downloads it and files it themselves — by calling 1930 or on cybercrime.gov.in. Also serves as their own written proof. |

There is no third document. The bank freeze letter was removed: the victim
cannot freeze anything (1930/CFCFRMS does that), and a bank notification is a
separate remedy that is out of scope for this build.

---

## 4. THE TWO SCENARIOS

**Act 1 — Guardian (during the call).** Live Hinglish scam call → STT streams
with word timestamps → guard layer detects OTP harvesting → **the victim's
outbound channel is severed** → counter-interrogate the caller (which number are
you calling from? RBI requires `1600xx`) → terminate + Hindi warning → Forensic
Incident Record: "₹0 LOST — attack prevented."

**Act 2 — RescueAgent (after the call — HERO).** Money already gone → victim
opens the mic and speaks Hinglish → warm agent classifies the fraud, extracts
entities, **asks aloud for anything missing** → the 1930 Complaint Draft is
built while they are still talking → real elapsed clock → victim downloads it
and files it manually.

**How the "call" works:** in this build the victim's call is a browser button
that opens the mic — real audio, real STT, real agent, the identical pipeline to
production. In production a helpline number (Exotel/Twilio) streams phone audio
into the same FastAPI. **Only the audio entry point differs.**

**Where the draft comes from.** The victim must speak. Act 1's transcript
supplies the caller's number, claimed identity, threat and OTP demand — evidence
and incident description. But the scammer never states the amount, the app or
the UTR, so **a financial complaint always requires Act 2.** One case record,
two sources.

---

## 5. LOCKED TECH STACK

| Layer | Choice | Verified |
|---|---|---|
| Frontend | React 18 + Vite 6 + Tailwind v4 | ✅ builds clean |
| Backend | Python + FastAPI (WebSockets — REQUIRED, see §6) | ✅ |
| DB | PostgreSQL 16 (Docker, host port **5433**) | ✅ |
| STT | AssemblyAI Streaming — **`universal-3-6-pro`**, SDK 1.5.5 | ⬜ Gate 0 unrun |
| LLM | Google Gemini Flash via **`models.generate_content`**, google-genai 2.25.0 | ✅ |
| TTS | edge-tts, MD5 disk cache + 4 pre-cached hero MP3s | ✅ 7ms cached / 1.9s cold |
| PDF | WeasyPrint 70, Noto Sans Devanagari **bundled in the repo** | ✅ conjuncts verified |

**Port 5433, not 5432.** A system Postgres on the default port collides
silently — you connect to the wrong database and the schema is simply absent.

**`models.generate_content`, not the `interactions` endpoint.** On a free-tier
429 the interactions endpoint *hangs* instead of returning the error;
`generate_content` surfaces it in under a second. A hang mid-call is
indistinguishable on screen from a dead product, and 429 is the free tier's
normal failure mode.

**Gemini's free-tier daily request quota is PER MODEL.** When one Flash model
is exhausted another still has budget, which is why `GEMINI_MODEL` is an env
var. A per-day 429 is deliberately **not** retried — it will not clear for
hours and retries only burn demo seconds. **Before a demo, switch
`GEMINI_MODEL` to a model you have not been testing on.**

**The Devanagari font is committed, not assumed.** Dev machines have it;
Render's Python image does not, and a dossier that renders as tofu boxes on
the deployed link is unrecoverable.

**`STT_ENABLED` defaults to false.** With a key present, every browser opening
`/ws/audio` would otherwise start a billed stream and a forgotten tab burns
credit silently. `STT_MAX_SESSION_SECONDS` (180) is the second net.

**Removed from the stack:** pgvector, sentence-transformers, AssemblyAI
pre-recorded. No vector search anywhere in this build.

**VOICE CASTING**
- RescueAgent / Guardian: `hi-IN-SwaraNeural` (female, warm)
- Scammer scenario segments: `hi-IN-MadhurNeural` (male — must be clearly
  distinguishable in demos and transcripts)

**LANGUAGE REACH.** `universal-3-6-pro` covers 32 languages with native
code-switching. Of Indian languages that is **Hindi, Marathi and Urdu** — so
Hinglish, Marathi-English and Urdu-English all work live, mid-sentence, in a
single pass. Tamil, Telugu, Bengali, Kannada, Malayalam, Gujarati, Punjabi and
Assamese are **not available on any streaming model** and are out of scope for
this build. Do not claim them.

**OUT OF SCOPE (do not build):** bank freeze letter · RAG / pgvector · sandbox
file upload (deferred) · AssemblyAI Voice Agent API · LLM Gateway · WhatsApp/SMS
APIs · fingerprint/immunity engine · warning dispatch · any auth/sign-in ·
fallback providers · any auto-submission to 1930 or banks · any "submitted" UI
claim.

---

## 6. DEPLOYMENT — two modes, env-var switched

The backend **cannot** live on Vercel: serverless functions do not hold a
WebSocket open, so WS#1 dies.

| Piece | DEMO MODE (stage) | PUBLIC MODE (judges' link) |
|---|---|---|
| React frontend | `npm run dev` | Vercel |
| FastAPI | localhost | Render free tier (WebSockets OK) |
| Postgres | local Docker | Neon or Supabase free tier |

Same codebase; only `DATABASE_URL` / `ALLOWED_ORIGINS` / base URLs change.

**PUBLIC MODE checklist:** Vercel **Deployment Protection must be OFF** or
judges hit a Vercel login wall. Share the production domain, not a
`git-<branch>-` preview URL. `VITE_WS_URL` must be `wss://` — an HTTPS page
cannot open a `ws://` socket. Verify with 2+ concurrent visitors.

---

## 7. ARCHITECTURE & CONNECTIONS

Exactly 2 WebSockets; everything else is plain HTTP.

```
WS#1 (we write):    React mic (16kHz PCM) ⇄ FastAPI /ws/audio ⇄ all UI events
WS#2 (SDK manages): FastAPI ⇄ AssemblyAI Streaming (universal-3-6-pro)
HTTP:               /api/tts · /api/case/{id}/docs · /api/health
```

**All API keys live ONLY in FastAPI env vars. Never in React.**

Rate limits: 5 streams/minute → reuse one stream, never rapid-reconnect.

### 7.1 THE CHANNEL CUT (replaces per-word bleeping)

**Per-word muting is impossible and must not be claimed.** STT returns a word
~300ms after it was spoken; by then that audio has already left the machine. A
word timestamp describes the past. You cannot un-send sound.

What we do instead:

1. The guard **ARMS** when threat state reaches `critical` — during the
   *scammer's* turn, where being slow is fine.
2. Once armed, the victim's outbound channel is **severed the instant local VAD
   detects them speaking**. Zero latency: no STT round trip, no per-word
   decision.
3. We mute **the channel, not the word**. We never need to know which word is a
   digit.
4. Word timestamps are then used for **evidence and display only** — rendering
   `••••••` in the transcript and proving in the forensic record that digits
   were spoken while the channel was cut.

The claim is: *"once OTP harvesting is detected, we sever the victim's audio
channel."* Buildable, honest, and stronger than per-word bleeping.

### 7.2 SANDBOX AUDIO INJECTION

Generate each scenario as a **sequence of MP3 segments** (one per speaker turn,
per §15). Never one mixed file.

Injection path: frontend decodes MP3 → AudioBuffer → resample to 16kHz mono
PCM16 → chunk → send over WS#1 **using the exact same code path as microphone
audio**. The pipeline cannot tell the difference — that is the point.

**FORBIDDEN:** playing the MP3 through speakers and re-capturing via mic (echo,
feedback, quality loss, broken word timestamps).

Audience playback: a parallel `<audio>` element plays the segment for the room.
The OTP segment's playback is muted at digit timestamps and a bleep tone plays
instead; the transcript shows `••••••`.

### 7.3 HALF-DUPLEX RULE (echo protection)

While agent TTS is playing, the frontend **pauses** sending PCM to WS#1; resume
300ms after playback ends. Without this the agent hears its own voice and loops
forever.

### 7.4 AUDIO FORMAT

Browser mic is 44.1/48kHz → downsample **client-side** (AudioWorklet) to 16kHz
PCM16 mono before WS#1.

---

## 8. ENVIRONMENT VARIABLES

```
ASSEMBLYAI_API_KEY=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash        # daily free quota is PER MODEL
DATABASE_URL=postgresql://suraksha:suraksha@localhost:5433/suraksha
TTS_VOICE_AGENT=hi-IN-SwaraNeural
TTS_VOICE_SCAMMER=hi-IN-MadhurNeural
ALLOWED_ORIGINS=http://localhost:5173,https://<project>.vercel.app

# CREDIT GUARD — false during development. True opens billed streams.
STT_ENABLED=false
STT_MAX_SESSION_SECONDS=180
```

---

## 9. WS#1 EVENT CONTRACT

Server → client (the client renders **only** from these):

```
{"type":"connection.status","service":"stt|gemini|db|tts","state":"standby|online|error"}
{"type":"transcript.partial","speaker":"scammer|victim|agent","text":"...","t":1.24}
{"type":"transcript.final","speaker":"...","text":"...","t":2.01}
{"type":"word.ts","word":"8","start":12.4,"end":12.6}
{"type":"threat.update","score":0,"state":"idle|scanning|suspicious|critical"}
{"type":"evidence.update","signals":[{"name":"OTP_EXTRACTION_DEMAND","desc":"...","confidence":0.996}]}
{"type":"guard.action","action":"guard_rules|counter_interrogate|channel_cut|terminate_call|warning_tts","ms":612}
{"type":"tool.call","name":"...","args":{}}
{"type":"tool.result","name":"...","ms":842,"result":{}}
{"type":"case.update","case_id":"GH-4821","fraud_type":"kyc_expiry_otp","confidence":0.987,"amount":40000,"app":"PhonePe","when_ago":"22 min","district":"Bhopal, MP"}
{"type":"doc.ready","doc":"1930|forensic","download_url":"/api/case/GH-4821/docs/1930.pdf"}
{"type":"tts.play","url":"/api/tts?text=..."}
{"type":"stat.update","key":"guard_loop|rescue_loop|redaction|stt_latency","value":"0.9s"}
{"type":"error","message":"..."}
```

Client → server: binary PCM chunks (16kHz mono), plus
`{"type":"mode","mode":"sandbox|live"}`,
`{"type":"scenario","id":"kyc|arrest|electricity"}`,
`{"type":"act","act":"intercept|rescue"}`.

---

## 10. GEMINI TOOLS (exactly these 4, strict JSON schemas, this order)

1. `classify_fraud(transcript)` → `{fraud_type, confidence}` — taxonomy:
   `digital_arrest | kyc_expiry_otp | parcel_customs | electricity_disconnect |
   investment_task | upi_collect | otp_screen_share | loan_app_harassment`
2. `extract_entities(transcript)` → `{amount, app, utr, when_ago, district,
   suspect_number}`
3. `create_case(...)` → `{case_id}` — starts the real elapsed clock
4. `draft_1930_report(case_id)` → `{fields:{...}, victim_statement_hi}` — a
   **complaint draft for the victim to file manually**. No submission exists.

`draft_freeze_letter` was removed.

### 10.1 — 1930 DRAFT FIELD POLICY

**AI-FILLED:** fraud category, amount, payment rail (app), date/time,
transaction reference (UTR, if spoken), suspect number, incident narrative
(Hindi statement).

**[FILL AT FILING]:** name, mobile, email, address, bank/account details, govt
ID — rendered as blank labelled fields. Plus a blank for the 14-digit
acknowledgement number the victim receives after filing.

**The call NEVER collects PII.** This is a privacy feature — say it in the
pitch. No submission action exists anywhere. Download only.

**A field that was not spoken stays empty and the agent asks for it aloud.**
Never infer a district, a bank or a UTR. A complaint with a hallucinated UTR is
worse than one with a blank UTR: it gets rejected and the window closes.

---

## 11. VERIFIED RIGHTS BLOCK (replaces the RAG spec)

The draft ends with a short, hand-verified block. It is **static text checked
against §2** — not model output, not retrieval:

```
YOUR RIGHTS — verified, with sources

• Tell your bank in writing today. Zero liability depends on when you
  notified them — 3 working days now, 5 calendar days from 1 Jan 2027.
• The bank must prove you were at fault, not the other way round.
• Sharing an OTP after being deceived is still covered from 1 Jan 2027.

  RBI (Commercial Banks – Responsible Business Conduct) Directions, 2025
  · Third Amendment Directions, 2026 (24 Jun 2026, in force 1 Jan 2027)
```

**No paragraph numbers are printed.** RBI's own PDF is CAPTCHA-blocked, and the
paragraph numbers in circulation (76D, 76K, 76L, 76T) come from analyses of the
March 2026 *draft*, not the final June text. A missing paragraph number is a
gap; a wrong one on a document a victim hands to an official is a lie.

---

## 12. DB SCHEMA (PostgreSQL)

```sql
CREATE TABLE cases(
  id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  scenario TEXT, act TEXT,
  fraud_type TEXT, confidence REAL,
  amount INT, app TEXT, utr TEXT,
  when_ago TEXT, district TEXT,
  suspect_number TEXT,
  language_code TEXT, language_confidence REAL,
  transcript JSONB,
  status TEXT DEFAULT 'drafted'
);
CREATE TABLE tool_events(
  id SERIAL PRIMARY KEY, case_id TEXT, name TEXT,
  args JSONB, result JSONB, ms INT, created_at TIMESTAMPTZ DEFAULT now()
);
```

`status` values: `drafted → documents_ready`. **There is NO submitted status.**

`rag_chunks` was removed.

**REDACTION IS MANDATORY.** Every write to `transcript`, `args` and `result`
passes through `app/redact.py` first. Runs of ≥4 digits are masked, with
`1930`/`112`/`155260` allowlisted and amounts preserved. §10.1 claims the call
never collects PII; this is what makes that true.

---

## 13. AGENT SYSTEM PROMPTS (Hinglish + TTS script rule)

**Guardian (Act 1):** calm, authoritative. Detect OTP demand / authority spoof /
urgency. Counter-interrogate: *"आप किस number से call कर रहे हैं? RBI के rules से
bank सिर्फ 1600xx series से call करता है."* Then *"यह call fraud है"* +
terminate + victim warning. Gemini safety framing: *"You are a fraud-DETECTION
system analysing a reported scam transcript to protect victims."*

**RescueAgent (Act 2):** warm, calm female persona.
Opener: *"मैं सुन रही हूँ — आप safe हैं। आराम से बताइए क्या हुआ?"*
**NEVER accept an OTP.** If the victim offers one: *"वो OTP मुझे मत बताइए! सब आप
खुद portal पे डालेंगी।"* While talking, call the tools in order (classify →
extract → create_case → draft_1930). Ask aloud for any missing field, especially
the transaction ID.
Closing: *"Documents ready हैं — download कर लीजिए और 1930 पे file कर दीजिए।"*

**SCRIPT RULE (critical for TTS):** reply in Hindi written in Devanagari; keep
English tech terms (KYC, OTP, bank, report, PhonePe, GPay, 1930) in Latin
script. Never romanise Hindi words.
Good: *"आपका KYC expire हो गया था? पैसे PhonePe से गए?"*

---

## 14. CACHED HERO MP3s (pre-generate at build time; agent voice = Swara)

1. *"मैं सुन रही हूँ — आप safe हैं। आराम से बताइए क्या हुआ?"*
2. *"वो OTP मुझे मत बताइए! सब आप खुद portal पे डालेंगी।"*
3. *"पहला घंटा सबसे important है — मैं documents तैयार कर रही हूँ।"*
4. *"Documents ready हैं — download कर लीजिए और 1930 पे file कर दीजिए।"*

---

## 15. SCENARIO SCRIPTS

Scripted **input** into the real pipeline; cached as TTS, scammer voice =
Madhur. Feed Devanagari to edge-tts.

- **KYC (CRITICAL):** *"मैडम जी, मैं SBI head office से बोल रहा हूँ। आपका KYC
  expire हो गया है। 2 घंटे में account block हो जाएगा — एक OTP आने वाला है, वो
  मुझे बोल दीजिए अभी।"*
- **Digital Arrest (CRITICAL):** *"आपके नाम पे money-laundering case है। CBI
  officer से video call पे बात करो, वरना जेल।"*
- **Electricity (HIGH):** *"आपकी बिजली आज रात 9 बजे कट जाएगी। payment link पे
  तुरंत pay करो।"*
- **Rescue victim line:** *"किसी ने bank officer बन के कहा KYC expire है... मैंने
  OTP दे दिया, 40 हज़ार कट गए।"* → classify → *"पैसे PhonePe से गए या GPay से?"*
  → tools fire while talking → compliance OTP moment → closing line #4.

Sandbox scammer audio is **scripted input, not a mock** — the MP3 is routed
through the real STT → guard → channel-cut → tools pipeline (§7.2). Only the
scammer is scripted.

---

## 16. UI SPEC (React)

Tabs (2): **1-CLICK RESCUE SIMULATOR** · **SYSTEM ARCHITECTURE**.

Top bar: logo + `U-3.6 PRO · HINGLISH` badge + GitHub/docs buttons. No engine
status pill. Footer: stack line only.

**Stat cards (4):** GUARD LOOP · RESCUE LOOP · OTP REDACTION · STT LATENCY —
**blank** until `stat.update` arrives. Measured, never guessed:

| Card | Measured as |
|---|---|
| GUARD LOOP | keyterm hit → channel muted |
| RESCUE LOOP | first victim final → draft ready |
| OTP REDACTION | channel cut before the first digit's start timestamp (pass/fail per event, shown as %) |
| STT LATENCY | chunk sent → first partial back |

**DEFENSE MODE row:** ADVERSARIAL SANDBOX + LIVE MICROPHONE TEST (red when
active) + EXPORT FORENSIC RECORD.

**Sandbox mode:** 3 scenario cards (KYC / Digital Arrest / Electricity) + big
SIMULATE button.

**Live mic mode:** START/STOP, STATUS: STANDBY→LISTENING, real Web Audio
AnalyserNode spectrum, suggested phrase *"Mera one-time passcode 8 4 2 1 9 0
hai"*.

**BLANK-STATE POLICY:** transcript, tool panel, evidence cards, case card,
documents, forensic modal, threat bar, clock — **all start empty** (dashed
empty-states). They fill ONLY from WS#1 events. **Never pre-fill any value in
code.**

**Case card:** TYPE / AMOUNT / WHEN blank → filled by `case.update`. Checklist
ends with "Document ready for download". **No submit item, ever.**

**Download:** ⬇ DOWNLOAD 1930 COMPLAINT DRAFT — disabled until `doc.ready`;
calls `GET /api/case/{id}/docs`. This is the only victim action in Act 2. Act
1's forensic record has its own export (JSON + PDF).

**Design tokens:** bg `#0D0A14`, panel `#16101F`, border `#2A2140`, amber
`#FFB224`, violet `#8B5CF6`, mint `#34D399`, red `#FF5470`. Fonts: Space Grotesk
(headings), Manrope (body), JetBrains Mono (transcripts/logs).

---

## 17. LATENCY LOGGING & STATS

Timestamp: first audio chunk, first partial, guard hit, each tool call/result,
TTS start. Compute the four values in §16 and push via `stat.update`. The clock
is **real wall-clock elapsed and uncapped** — if it takes 40 seconds, it shows
40 seconds.

---

## 18. HONESTY LIST (the only genuinely simulated things — pitch + [SIM] chips)

1. **1930 auto-filing does not exist.** No public API; the portal needs the
   victim's own credentials; the product deliberately prepares a draft for
   manual filing.
2. **The channel cut has no outbound leg in this build.** Mic → our backend.
   "The scammer never hears it" describes the production telephony path — an
   entry-point substitution, not a fake.
3. **Browser mic instead of a phone line** — entry-point substitution;
   production streams telephony into the same backend.

**NOT mocks (say this confidently):** STT pipeline, guard logic, channel cut,
counter-interrogation, Gemini tools, document generation, download flow, digit
redaction. Sandbox audio is scripted **input** to the real pipeline (§7.2).

---

## 19. BUILD ORDER

| | Batch | Status |
|---|---|---|
| ⬜ | **GATE 0** — stream a §15 clip through `universal-3-6-pro`, dump raw messages. Answers: Devanagari or romanised? do `words[]` arrive on partials? measured latency. **No guard rule may be written before this.** | **blocks D** |
| ✅ | **A** — Docker Postgres + `cases`/`tool_events` + async pool, every write through `redact.py` | done |
| ✅ | **B** — Gemini + 4 tools + rescue orchestrator → Act 2 end to end | done |
| ✅ | **C** — WeasyPrint PDF + `GET /api/case/{id}/docs` | done |
| ⬜ | **D** — Act 1: sandbox injection, guard rules from the Gate 0 fixture, the `1600xx` check, channel cut, forensic record | blocked |
| ✅ | **E** — edge-tts + cached hero MP3s + half-duplex | done |
| ⬜ | **F** — PUBLIC MODE deploy + 2-user concurrency test | |
| ⬜ | **G** — Polish, `[SIM]` chips, latency stats, README | |

Act 2 is built before Act 1 because it needs nothing but a mic, so it is
demoable the day it is done.

**Everything up to here was built and tested without spending AssemblyAI
credit.** Act 2's whole pipeline is exercised by `scripts/test_rescue.py`,
which feeds scripted victim turns straight into the orchestrator in place of
`transcript.final` events.

---

## 20. SOURCES FOR §2

- RBI, *Customer Protection – Limiting Liability of Customers in Unauthorised
  Electronic Banking Transactions*, RBI/2017-18/15, 6 Jul 2017 —
  `rbi.org.in/Scripts/NotificationUser.aspx?Id=11040`
- RBI press release, *Amendment Directions on Review of Framework of Limiting
  Customer Liability in Digital Transactions*, 24 Jun 2026 —
  `rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63011`
- RBI, *Prevention of financial frauds perpetrated using voice calls and SMS*,
  17 Jan 2025 — the `1600xx` mandate
- I4C, National Cybercrime Reporting Portal — `i4c.mha.gov.in/ncrp.aspx`
- AssemblyAI, streaming model selection —
  `assemblyai.com/docs/streaming/select-the-speech-model`
- AssemblyAI, multilingual streaming (32-language list) —
  `assemblyai.com/docs/streaming/universal-streaming/multilingual-transcription`

---

## 21. CHANGE LOG — 2026-09-30

| # | Change | Why |
|---|---|---|
| 1 | Bank freeze letter **removed** | The victim cannot freeze anything — 1930/CFCFRMS does. The name was wrong and the remedy is out of scope. |
| 2 | pgvector, RAG, sentence-transformers, `rag_chunks` **removed** | With no freeze letter there is nothing to cite. Replaced by §11's verified rights block. |
| 3 | Corpus source "RBI Master Direction on Customer Protection (Nov 2023)" **deleted** | **That document does not exist.** |
| 4 | 5 Gemini tools → **4** | `draft_freeze_letter` removed. |
| 5 | Per-word bleep → **channel cut** (§7.1) | Per-word muting is physically impossible; a timestamp describes the past. |
| 6 | `T+3:40` target **deleted** | Invented number. Real elapsed time is faster, and true. |
| 7 | `universal-3-5-pro` → **`universal-3-6-pro`** | Current flagship; adds Marathi + Urdu at no cost. |
| 8 | §2 rewritten against primary sources | The previous version had an invented RBI document and no `1600xx`, CFCFRMS or Section DA. |
| 9 | Digit redaction made **mandatory** before persistence (§12) | §10.1's "never collects PII" was otherwise false. |
| 10 | Language reach stated explicitly (§5) | Hindi/Marathi/Urdu live; the other eight Indian languages are not on any streaming model. Do not claim them. |
| 11 | Deployment Protection + `wss://` added to §6 | The deployed frontend was behind a Vercel login wall. |
| 12 | Sandbox **file upload** deferred | Deliberate scope cut; the §7.2 path already supports it when we want it. |

### Decisions taken during the build (batches A–E)

| # | Decision | Why |
|---|---|---|
| 13 | Postgres on **5433**, plain `postgres:16-alpine` | 5432 collides silently with a system Postgres. pgvector image dropped with the corpus. |
| 14 | `status` is a **CHECK constraint**, not a convention | The never-file rule is now enforced by the database. A refactor cannot create a "filed" case. |
| 15 | `utr` is the one **redaction-exempt** key | It is 12 digits so the masker would eat it, but it authorises nothing and a complaint without it is rejected at the counter. |
| 16 | `STT_ENABLED` credit guard, default off | A key in `.env` otherwise means every page load opens a billed stream. |
| 17 | Gemini via `models.generate_content`; `GEMINI_MODEL` env var; per-day 429 not retried | The `interactions` endpoint hangs on a 429. Daily quota is per model. |
| 18 | **OTP guardrail enforced in code**, not only in the prompt | A long emotional code-switched conversation is exactly where a system prompt gets forgotten. Cue word + digit run → refuse before the model sees the turn. |
| 19 | Draft waits until every question has been **asked**, not answered | Drafting on the first two facts froze a document with `utr` and `district` blank because those answers came two turns later. |
| 20 | `doc.ready` announced wherever the draft appears | The model calls `draft_1930_report` on its own initiative sometimes; the document was being produced with no event. |
| 21 | The draft is **persisted on the case row** | The victim downloads it after the call has ended, not during. |
| 22 | Noto Sans Devanagari **committed to the repo** | Render's image has no Devanagari font; tofu boxes on the deployed link are unrecoverable. |
| 23 | Four hero MP3s **committed**, cache keyed on voice+text | Cold synthesis is 1.9s; the opener must be instant. edge-tts is unauthenticated and will rate-limit. |
| 24 | TTS failure returns **503, not 500** | Losing the voice must never lose the conversation — the agent's words are already on screen. |
| 25 | `websockets` pinned `>=13,<17` | google-genai caps it below 17, assemblyai needs ≥11; an unpinned resolve on Render could satisfy neither. |
