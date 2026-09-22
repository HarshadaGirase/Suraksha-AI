/** SYSTEM ARCHITECTURE tab (CLAUDE.MD §16, §7). */

import { SecTitle } from "./ui.jsx";

const STAGES = [
  ["STAGE 01", "Hinglish Streaming Engine",
   "React mic → FastAPI /ws/audio → AssemblyAI Universal-3.5 Pro Streaming. Partials plus word timestamps feed the transcript and the forensic record."],
  ["STAGE 02", "Guard + Rescue Intent (Gemini)",
   "Keyterm rules fire on partials; Gemini Flash classifies India's 8-scam taxonomy on finals and drives both agents — Guardian (intercept) and RescueAgent (file)."],
  ["STAGE 03", "Tool Calling & Document Dispatch",
   "5 JSON-schema tools: classify → extract → create_case → draft_1930 → draft_freeze (RAG-cited). The victim downloads the dossier — filing is manual by design."],
];

export default function Architecture() {
  return (
    <div>
      <SecTitle>SURAKSHAAI MULTI-TIER LIFECYCLE DEFENSE ARCHITECTURE</SecTitle>
      <div className="mb-[14px] grid gap-3 md:grid-cols-3">
        {STAGES.map(([no, name, body]) => (
          <div key={no} className="rounded-[10px] border border-line border-t-[3px] border-t-amber bg-panel p-[15px]">
            <div className="text-[8.5px] font-extrabold tracking-[2px] text-danger">{no}</div>
            <div className="my-[6px] text-[13px] font-extrabold">{name}</div>
            <p className="text-[10.5px] leading-[1.65] text-muted">{body}</p>
          </div>
        ))}
      </div>

      <div className="rounded-[10px] border border-line bg-panel2 p-4 font-mono">
        {[
          ["[ Browser Mic (React) ]", "WS#1 /ws/audio — 16kHz PCM16, downsampled client-side"],
          ["[ AssemblyAI U-3.5 Pro ]", "partials · finals · word timestamps"],
          ["[ Guard keyterm rules ]", "threat intent confirmed"],
          ["[ Predictive channel cut ]", "victim audio severed before digits leave"],
          ["[ classify → extract → create ]", "case opened, facts locked"],
          ["[ draft_1930 · draft_freeze ]", "documents ready to download"],
        ].map(([left, right]) => (
          <div key={left} className="text-[11px] leading-[2.15]">
            {left} ─► <b className="text-amber">{right}</b>
          </div>
        ))}
      </div>

      <div className="mt-[14px] rounded-lg border border-violet/45 bg-violet/15 px-[14px] py-3 text-[10px] leading-[1.65] text-[#C4B0FF]">
        📡 CONNECTION TRUTH: 2 WebSockets total — WS#1 (React ↔ FastAPI, ours) · WS#2 (FastAPI ↔
        AssemblyAI, SDK-managed). TTS is plain HTTP /api/tts. No Voice Agent API, no LLM Gateway.
      </div>

      <div className="mt-[14px] rounded-lg border border-amber/45 bg-amber/15 px-[14px] py-3 text-[10px] leading-[1.7] text-amber">
        ⚠ WHY THE CHANNEL IS CUT, NOT THE WORD: STT word timestamps describe audio that has
        already been sent. A per-word mute can never un-send a digit. So the guard arms on threat
        and severs the victim's outbound channel on local VAD — no network round trip. Word
        timings are used for evidence and for rendering ••••••, never as the trigger.
      </div>
    </div>
  );
}
