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
          <div className="flex h-10 w-10 items-center justify-center rounded-[11px] bg-gradient-to-br from-amber to-amber2 text-xl shadow-[0_0_22px_rgba(255,178,36,.13)]">
            ⏱
          </div>
          <div>
            <h1 className="font-display text-[21px]">
              Suraksha<i className="not-italic text-amber">AI</i>
              <span className="ml-2 rounded-md border border-violet/40 bg-violet/15 px-[9px] py-[3px] align-middle text-[9px] font-extrabold tracking-[1px] text-[#C4B0FF]">
                U-3.6 PRO · HINGLISH
              </span>
            </h1>
            <div className="mt-[2px] text-[11px] text-faint">
              Voice Guardian &amp; Fraud Rescue Network — intercept live scams · rescue victims in
              the golden hour
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
