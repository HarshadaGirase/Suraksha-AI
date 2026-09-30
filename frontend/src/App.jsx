import { useCallback, useEffect, useRef, useState } from "react";
import Architecture from "./components/Architecture.jsx";
import Simulator from "./components/Simulator.jsx";
import { Tab } from "./components/ui.jsx";
import { useMic } from "./lib/useMic.js";
import { useSurakshaSocket } from "./lib/useSurakshaSocket.js";
import { useTts } from "./lib/useTts.js";

export default function App() {
  const [tab, setTab] = useState("sim");
  const [mode, setMode] = useState("mic");
  const [scenario, setScenario] = useState("kyc");

  // §7.3 half-duplex: TTS playback holds the mic. There is a cycle here —
  // useTts needs mic.setMuted, and useMic needs bus.sendAudio which comes from
  // the socket the TTS listener is attached to — so the mic is reached through
  // a ref rather than a dependency. setMuted stays referentially stable, which
  // keeps useTts from re-creating its queue on every render.
  const micRef = useRef(null);
  const setMuted = useCallback((v) => micRef.current?.setMuted(v), []);
  const tts = useTts(setMuted);

  const playTts = tts.play;
  const onEvent = useCallback(
    (ev) => {
      if (ev.type === "tts.play") playTts(ev.url);
    },
    [playTts],
  );

  // Local VAD from the worklet. The mute already happened on the audio thread
  // by the time this fires (§7.1) — this only reports it, so the backend can
  // record the cut and measure the guard loop.
  const busRef = useRef(null);
  const onVad = useCallback((speaking) => {
    busRef.current?.sendControl({ type: "vad", speaking });
  }, []);

  const bus = useSurakshaSocket(onEvent);
  const mic = useMic(bus.sendAudio, onVad);
  micRef.current = mic;
  busRef.current = bus;

  // Arm the worklet the moment the backend says the threat is confirmed.
  // Arming is cheap and reversible; the cut itself costs nothing until the
  // victim actually speaks.
  useEffect(() => {
    mic.setArmed(bus.threat.state === "critical");
  }, [mic, bus.threat.state]);

  return (
    <div className="px-4 pb-12 pt-[18px] md:px-[30px]">
      <header className="mb-[14px] flex items-start gap-[14px]">
        <div className="flex items-center gap-[11px]">
          {/* The mark is the product: a shield containing a voice waveform
              that stops dead at a cut line. Same artwork as the favicon. */}
          <svg
            viewBox="0 0 64 64"
            className="h-10 w-10 shrink-0 rounded-[11px] shadow-[0_0_22px_rgba(255,178,36,.13)]"
            role="img"
            aria-label="SurakshaAI"
          >
            <defs>
              <linearGradient id="logoG" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#FFB224" />
                <stop offset="100%" stopColor="#8B5CF6" />
              </linearGradient>
            </defs>
            <rect width="64" height="64" rx="14" fill="#16101F" />
            <path
              d="M32 9 L51 16 v15c0 12-8 20-19 24-11-4-19-12-19-24V16z"
              fill="none"
              stroke="url(#logoG)"
              strokeWidth="3.2"
              strokeLinejoin="round"
            />
            <g stroke="#FFB224" strokeWidth="3" strokeLinecap="round">
              <line x1="22" y1="28" x2="22" y2="38" />
              <line x1="27" y1="24" x2="27" y2="42" />
              <line x1="32" y1="20" x2="32" y2="46" />
            </g>
            <g stroke="#2A2140" strokeWidth="3" strokeLinecap="round">
              <line x1="37" y1="32" x2="37" y2="34" />
              <line x1="42" y1="32" x2="42" y2="34" />
            </g>
            <line
              x1="34.5" y1="17" x2="34.5" y2="49"
              stroke="#FF5470" strokeWidth="2.4" strokeLinecap="round"
            />
          </svg>
          <div>
            <h1 className="font-display text-[21px]">
              Suraksha<i className="not-italic text-amber">AI</i>
              <span className="ml-2 rounded-md border border-violet/40 bg-violet/15 px-[9px] py-[3px] align-middle text-[9px] font-extrabold tracking-[1px] text-[#C4B0FF]">
                U-3.6 PRO · HINGLISH
              </span>
            </h1>
            <div className="mt-[2px] text-[11px] text-faint">
              Voice Guardian &amp; Fraud Rescue Agent — sever the channel mid-scam · draft the
              1930 complaint while they talk
            </div>
          </div>
        </div>
      </header>

      <div className="mb-[14px] rounded-[10px] border border-violet/45 bg-violet/15 px-[17px] py-[13px] text-[13px] leading-[1.65]">
        ⏺ <b className="text-[#C4B0FF]">Core Mission:</b> SurakshaAI intercepts live Hinglish
        OTP-harvesting calls — <b>severing the victim's channel before the code reaches the
        scammer</b> — and for those without any guardian, it <b>rescues victims after the scam</b>:
        a 1930 complaint draft, ready to file.
      </div>

      <div role="tablist" className="mb-4 flex gap-[10px]">
        <Tab active={tab === "sim"} onClick={() => setTab("sim")}>
          ⚡ 1-CLICK RESCUE SIMULATOR
        </Tab>
        <Tab active={tab === "arch"} onClick={() => setTab("arch")}>
          ⚙ SYSTEM ARCHITECTURE
        </Tab>
      </div>

      {tab === "sim" ? (
        <Simulator
          bus={bus}
          mic={mic}
          tts={tts}
          mode={mode}
          setMode={setMode}
          scenario={scenario}
          setScenario={setScenario}
        />
      ) : (
        <Architecture />
      )}

      <footer className="mt-[22px] text-center text-[9.5px] leading-[1.9] tracking-[1px] text-faint">
        SURAKSHA AI — React + FastAPI + PostgreSQL + AssemblyAI Universal-3.6 Pro Streaming + Gemini
        Flash + edge-tts + WeasyPrint
      </footer>
    </div>
  );
}
