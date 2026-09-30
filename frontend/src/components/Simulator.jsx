/**
 * 1-CLICK RESCUE SIMULATOR (CLAUDE.MD §16).
 *
 * Every live-data zone starts blank and fills only from WS#1 events. The
 * mockup hardcoded values like "98.7%", "₹40000" and the evidence confidence
 * percentages directly into markup, which contradicted its own BLANK-STATE
 * POLICY; here those can only come from tool.result / evidence.update.
 */

import { useMemo } from "react";
import { Badge, BigButton, Card, Empty, Mini, SecTitle, SimChip } from "./ui.jsx";

const STATS = [
  ["guard_loop", "⚡ GUARD LOOP", "keyterm hit → channel cut"],
  ["rescue_loop", "⏱ RESCUE LOOP", "first word → dossier ready"],
  ["redaction", "🔐 OTP REDACTION", "scammer never hears digits"],
  ["stt_latency", "🎙 STT LATENCY", "chunk → partial transcript"],
];

const INFRA = [
  ["stt", "Streaming STT", "AssemblyAI Universal-3.6 Pro · 16kHz WebSocket · partials + word timestamps."],
  ["gemini", "Guard Intent Engine", "Keyterm rules on partials + Gemini classification on finals."],
  ["gemini", "Gemini Tool Calling", "4 JSON-schema tools: classify · extract · create_case · draft_1930."],
  ["db", "Case Record", "PostgreSQL. Digit runs are masked before anything is written."],
];

const SCENARIOS = [
  { id: "kyc", tag: "CRITICAL", num: "+91 98••••", title: "🏦 KYC Expiry — OTP Harvesting",
    quote: "SBI head office se bol raha hoon, KYC expire hai, OTP batao warna account block" },
  { id: "arrest", tag: "CRITICAL", num: "+91 87••••", title: "🚨 Digital Arrest — Fake CBI",
    quote: "Aapke naam pe money-laundering case hai, video call pe aao, jail se bachna hai" },
  { id: "electricity", tag: "HIGH", num: "+91 78••••", title: "⚡ Electricity Disconnect",
    quote: "Aaj raat 9 baje tak bijli kat jayegi — payment link pe turant pay karo" },
];

const CONN_LABEL = {
  idle: ["STATUS: STANDBY", "border-line text-faint"],
  connecting: ["CONNECTING…", "border-amber/40 bg-amber/15 text-amber"],
  open: ["CONNECTED", "border-mint/40 bg-mint/10 text-mint"],
  // Render's free tier idles down after ~15 min and takes roughly 50s to wake.
  // A judge opening a cold link sees a failing socket and reads the project as
  // broken, so the reconnect state says what is actually happening (PLAN.md
  // open risks).
  reconnecting: [
    "WAKING BACKEND… (up to 50s on free tier)",
    "border-amber/40 bg-amber/15 text-amber animate-pulse-soft",
  ],
  error: ["CONNECTION ERROR", "border-danger/40 bg-danger/15 text-danger"],
};

export default function Simulator({ bus, mic, mode, setMode, scenario, setScenario }) {
  const [connText, connCls] = CONN_LABEL[bus.connection] || CONN_LABEL.idle;

  const threatColor =
    bus.threat.score >= 75 ? "text-danger" : bus.threat.score >= 40 ? "text-amber" : "text-faint";

  const lines = useMemo(
    () => (bus.partial ? [...bus.finals, { ...bus.partial, live: true }] : bus.finals),
    [bus.finals, bus.partial],
  );

  return (
    <div>
      {/* ---------------------------------------------------- stat cards */}
      <div className="mb-4 grid gap-3 md:grid-cols-4">
        {STATS.map(([key, label, sub]) => {
          const value = bus.stats[key];
          return (
            <Card key={key}>
              <div className="text-[9.5px] tracking-[1.5px] text-faint">{label}</div>
              <div
                className={`my-[6px] font-display text-[30px] font-bold ${
                  value ? "text-amber" : "text-faint"
                }`}
              >
                {value || "—"}
              </div>
              <div className="text-[10.5px] text-faint">{sub}</div>
            </Card>
          );
        })}
      </div>

      {/* ---------------------------------------------------- infra */}
      <SecTitle>ACTIVE SECURITY INFRASTRUCTURE STACK</SecTitle>
      <div className="mb-4 grid gap-3 md:grid-cols-4">
        {INFRA.map(([svc, name, desc]) => (
          <div key={svc} className="rounded-[10px] border border-line bg-panel px-[15px] py-[13px]">
            <div className="flex items-center justify-between text-xs font-bold">
              <span>{name}</span>
              <Badge tone={bus.services[svc]}>{(bus.services[svc] || "standby").toUpperCase()}</Badge>
            </div>
            <p className="mt-[7px] text-[10px] leading-[1.55] text-faint">{desc}</p>
          </div>
        ))}
      </div>

      {/* ---------------------------------------------------- mode row */}
      <div className="mb-4 flex flex-wrap items-center gap-[10px]">
        <span className="text-[9.5px] tracking-[2px] text-faint">DEFENSE MODE:</span>
        <Mini
          onClick={() => setMode("sandbox")}
          className={mode === "sandbox" ? "border-amber/50 bg-amber/15 !text-amber" : ""}
        >
          🧪 ADVERSARIAL SANDBOX
        </Mini>
        <Mini
          onClick={() => setMode("mic")}
          className={mic.active ? "border-danger bg-danger !text-white" : mode === "mic" ? "border-amber/50 bg-amber/15 !text-amber" : ""}
        >
          🎙 LIVE MICROPHONE TEST
        </Mini>
        <span className="flex-1" />
        <span className={`rounded-lg border px-[10px] py-[3px] text-[9.5px] font-extrabold tracking-[1px] ${connCls}`}>
          {connText}
        </span>
      </div>

      {/* ---------------------------------------------------- sandbox */}
      {mode === "sandbox" && (
        <div className="mb-4 rounded-xl border border-line bg-panel2 p-[18px]">
          <b className="text-[13px] tracking-[1px]">
            ⚡ 1-CLICK INTERACTIVE <i className="not-italic text-amber">FRAUD INTERCEPT &amp; RESCUE SANDBOX</i>
          </b>
          <p className="mb-[14px] mt-1 text-[10.5px] text-faint">
            Select an India-specific scenario → full lifecycle: live channel cut + counter-interrogation,
            then golden-hour rescue
          </p>
          <div className="mb-3 grid gap-3 md:grid-cols-3">
            {SCENARIOS.map((s) => (
              <button
                key={s.id}
                type="button"
                aria-pressed={scenario === s.id}
                onClick={() => setScenario(s.id)}
                className={`cursor-pointer rounded-[10px] border bg-panel p-[14px] text-left transition ${
                  scenario === s.id ? "border-danger" : "border-line hover:border-danger/60"
                }`}
              >
                <div className="flex justify-between text-[8.5px] tracking-[1px]">
                  <span className={`rounded-lg px-2 py-[2px] font-extrabold ${
                    s.tag === "CRITICAL" ? "bg-danger/15 text-danger" : "bg-amber/15 text-amber"
                  }`}>
                    {s.tag} THREAT
                  </span>
                  <span className="font-mono text-faint">{s.num}</span>
                </div>
                <b className="mb-[5px] mt-2 block text-[13px]">{s.title}</b>
                <span className="text-[11px] italic leading-[1.55] text-muted">“{s.quote}”</span>
              </button>
            ))}
          </div>
          <p className="mb-3 text-[10.5px] text-faint">
            🎯 Rescue Target: <b className="text-muted">NCRP 1930 Cyber-Fraud Portal</b> (portal
            submission is not part of this build<SimChip />) · <b className="text-muted">Bank Fraud Desk</b>
          </p>
          <BigButton disabled className="bg-panel text-faint">
            ▶ SANDBOX INJECTION — ARRIVES IN M4
          </BigButton>
        </div>
      )}

      {/* ---------------------------------------------------- live mic */}
      {mode === "mic" && (
        <div className="mb-4 rounded-xl border border-line bg-panel2 p-[18px]">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-[10px]">
            <div>
              <h3 className="font-display text-[13.5px] tracking-[1px]">
                🎙 LIVE INTERACTIVE MICROPHONE DEFENSE TEST
              </h3>
              <p className="mt-1 text-[10.5px] text-faint">
                Speak to test real-time Hinglish ingestion through the full pipeline.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={mic.active ? mic.stop : mic.start}
                disabled={bus.connection !== "open"}
                className={`cursor-pointer rounded-[9px] px-[22px] py-3 font-display text-[12.5px] font-extrabold tracking-[1px] disabled:cursor-not-allowed disabled:opacity-45 ${
                  mic.active ? "border border-line bg-panel text-muted" : "border-none bg-danger text-white"
                }`}
              >
                {mic.active ? "⏹ STOP MIC TEST" : "🎤 START LIVE MIC TEST"}
              </button>
              <Mini onClick={bus.reset} aria-label="Reset transcript">⟲</Mini>
            </div>
          </div>
          <div className="flex items-center justify-between rounded-[9px] border border-line bg-panel px-[15px] py-[11px] text-xs text-muted">
            <span>
              Suggested Test Phrase:{" "}
              <b className="font-mono text-[11.5px] text-amber">“Mera one-time passcode 8 4 2 1 9 0 hai”</b>
            </span>
            <span className={`rounded-lg border px-[10px] py-[3px] text-[9.5px] font-extrabold tracking-[1px] ${
              mic.active ? "border-danger/40 bg-danger/15 text-danger animate-pulse-soft" : "border-line text-faint"
            }`}>
              {mic.active ? "LISTENING" : "STANDBY"}
            </span>
          </div>
          {mic.error && (
            <p className="mt-2 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-[11px] text-danger">
              {mic.error}
            </p>
          )}
        </div>
      )}

      {/* ---------------------------------------------------- threat bar */}
      <div className="mb-4 flex items-center gap-[14px] rounded-[10px] border border-line bg-panel px-4 py-3">
        <span className="text-[9.5px] tracking-[2px] text-faint">THREAT LEVEL</span>
        <div className="h-[11px] flex-1 overflow-hidden rounded-lg border border-line bg-panel2">
          <div
            className="h-full rounded-lg bg-gradient-to-r from-amber to-danger transition-[width] duration-700"
            style={{ width: `${bus.threat.score}%` }}
          />
        </div>
        <span className={`min-w-[170px] text-right font-display text-[19px] font-bold ${threatColor}`}>
          {bus.threat.state === "idle" ? "— IDLE" : `${bus.threat.score} — ${bus.threat.state.toUpperCase()}`}
        </span>
      </div>

      {/* ---------------------------------------------------- spectrum */}
      <div className="mb-4 rounded-[10px] border border-line bg-panel px-4 py-[13px]">
        <div className="mb-[10px] flex flex-wrap justify-between gap-[6px] text-[9.5px] tracking-[1.5px] text-faint">
          <span>🔊 LIVE VOICE SPECTRUM — STREAMING STT</span>
          {mic.active && (
            <span className="rounded-lg bg-danger/15 px-[9px] py-[2px] text-[8.5px] font-extrabold text-danger">
              INCOMING · VAD ACTIVE
            </span>
          )}
        </div>
        <div className="flex h-[42px] items-end gap-[4px]">
          {mic.levels.map((v, i) => (
            <i
              key={i}
              className="flex-1 rounded-sm bg-amber opacity-75"
              style={{ height: `${Math.max(8, v * 100)}%` }}
            />
          ))}
        </div>
        <div className="mt-[9px] flex justify-between text-[9.5px] text-faint">
          <span className="font-mono">websocket: /ws/audio · 16kHz PCM</span>
          <span>{mic.active ? "🎧 capture: ACTIVE" : "🎧 capture: STANDBY"}</span>
        </div>
      </div>

      {/* ---------------------------------------------------- transcript + tools */}
      <div className="mb-4 grid gap-[14px] lg:grid-cols-[1.3fr_1fr]">
        <Card>
          <SecTitle>🎙 LIVE CALL AUDIO STREAM — HINGLISH</SecTitle>
          {lines.length === 0 ? (
            <Empty icon="🎤">
              Transcript streams here, word-by-word.
              <br />
              Switch to <b>LIVE MICROPHONE TEST</b> and speak.
            </Empty>
          ) : (
            <div>
              {lines.map((l, i) => (
                <div
                  key={i}
                  className={`mb-[9px] rounded-[10px] border px-[14px] py-[11px] text-[12.5px] leading-[1.65] ${
                    l.speaker === "agent"
                      ? "border-mint/30 bg-mint/10"
                      : "border-danger/30 bg-danger/10"
                  } ${l.live ? "opacity-70" : ""}`}
                >
                  <span className={`mb-1 block text-[9px] font-extrabold tracking-[1.5px] ${
                    l.speaker === "agent" ? "text-mint" : "text-danger"
                  }`}>
                    {l.speaker.toUpperCase()} · T+{l.t?.toFixed?.(2) ?? "0.00"}
                    {l.live ? " · live" : ""}
                  </span>
                  {l.text}
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <SecTitle>⚙ AGENT ACTION &amp; TOOL EXECUTIONS</SecTitle>
          {bus.tools.length === 0 && bus.guard.length === 0 ? (
            <Empty icon="⚙" className="py-[22px]">Tools appear here as the agent acts.</Empty>
          ) : (
            <div>
              {bus.guard.map((g, i) => (
                <div key={`g${i}`} className="mb-[7px] rounded-r-lg border-l-[3px] border-violet bg-panel2 px-[11px] py-[7px] font-mono text-[10.5px]">
                  <span className="text-amber">{g.action}()</span>
                  <span className="float-right text-mint">{g.ms}ms ✓</span>
                </div>
              ))}
              {bus.tools.map((t, i) => (
                <div key={`t${i}`} className="mb-[7px] rounded-r-lg border-l-[3px] border-mint bg-panel2 px-[11px] py-[7px] font-mono text-[10.5px]">
                  <span className="text-amber">{t.name}()</span>
                  <span className={`float-right ${t.status === "done" ? "text-mint" : "text-faint"}`}>
                    {t.status === "done" ? `${t.ms}ms ✓` : "⏳"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ---------------------------------------------------- evidence */}
      <SecTitle>EXPLAINABLE THREAT FORENSICS &amp; DETECTION EVIDENCE</SecTitle>
      <div className="mb-[18px] grid gap-3 md:grid-cols-4">
        {bus.evidence.length === 0 ? (
          <div className="md:col-span-3">
            <Empty icon="🔍">Detection signals appear after classification.</Empty>
          </div>
        ) : (
          bus.evidence.map((s, i) => (
            <div key={i} className="rounded-lg border border-line border-l-[3px] border-l-danger bg-panel px-[14px] py-3">
              <span className="float-right font-display text-[13px] font-extrabold text-danger">
                {(s.confidence * 100).toFixed(1)}%
              </span>
              <b className="block text-[11px] tracking-[.5px]">{s.name}</b>
              <small className="mt-1 block text-[9.5px] leading-[1.5] text-faint">{s.desc}</small>
            </div>
          ))
        )}
        <div className="rounded-lg border border-violet/45 bg-violet/15 px-[14px] py-3 text-[10px] leading-[1.65] text-[#C4B0FF]">
          🧠 DECISION GROUNDING
          <br />
          Keyterm rules on partials + Gemini structured JSON on finals · Zero credentials captured by AI
        </div>
      </div>

      {/* ---------------------------------------------------- case + docs */}
      <SecTitle>🚑 GOLDEN-HOUR RESCUE OUTPUT</SecTitle>
      <div className="grid gap-[14px] lg:grid-cols-[1.25fr_.9fr_1fr]">
        <Card>
          <SecTitle>📋 CASE CARD</SecTitle>
          <div className="font-mono text-[10.5px] leading-[2.1] text-faint">
            TYPE&nbsp;&nbsp;&nbsp;<b className={bus.kase?.fraud_type ? "text-mint" : ""}>{bus.kase?.fraud_type || "—"}</b>
            <br />
            AMOUNT&nbsp;<b className={bus.kase?.amount ? "text-mint" : ""}>
              {bus.kase?.amount ? `₹${bus.kase.amount.toLocaleString("en-IN")}` : "—"}
            </b>
            <br />
            WHEN&nbsp;&nbsp;&nbsp;<b className={bus.kase?.when_ago ? "text-mint" : ""}>{bus.kase?.when_ago || "—"}</b>
          </div>
          <hr className="my-[10px] border-line" />
          <BigButton
            disabled={!bus.docs["1930"]}
            className={bus.docs["1930"] ? "bg-amber text-bg" : "bg-panel2 text-faint"}
            onClick={() => {
              const url = bus.docs["1930"]?.download_url;
              if (url) window.open(url, "_blank", "noopener");
            }}
          >
            ⬇ DOWNLOAD 1930 COMPLAINT DRAFT
          </BigButton>
        </Card>

        <Card>
          <div className="mb-2 text-[11px] font-extrabold tracking-[.5px] text-amber">
            📄 1930 / NCRP REPORT — DRAFT
          </div>
          {bus.docs["1930"] ? (
            <p className="text-[10.5px] leading-[1.75] text-muted">
              ✓ Draft ready — not filed. You file it yourself.
            </p>
          ) : (
            <Empty>Draft appears after draft_1930_report() executes</Empty>
          )}
        </Card>

        <Card>
          <div className="mb-2 text-[11px] font-extrabold tracking-[.5px] text-amber">
            ⚖ YOUR RIGHTS — PRINTED ON THE DRAFT
          </div>
          {bus.docs["1930"] ? (
            <div className="rounded-md border-l-[3px] border-amber bg-amber/15 px-[11px] py-[7px] text-[9.5px] leading-[1.7] text-amber">
              Tell your bank in writing today — zero liability depends on when you told them.
              The bank must prove you were at fault, not the other way round.
              <div className="mt-[6px] text-[8.5px] text-faint">
                RBI (Responsible Business Conduct) Directions, 2025 · Third Amendment
                Directions, 2026
              </div>
            </div>
          ) : (
            <Empty>Rights summary appears with the draft</Empty>
          )}
        </Card>
      </div>
    </div>
  );
}
