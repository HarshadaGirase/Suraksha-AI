/**
 * WS#1 client (CLAUDE.MD §9).
 *
 * §16's BLANK-STATE POLICY: every field below starts empty and is only ever
 * written from a server event. Nothing here invents a value, which is why the
 * initial state has no numbers in it at all.
 *
 * Adds the reconnect/visible-connection state the spec's event contract never
 * covered (PLAN.md C11) — conference wifi and Render's cold start both need it.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const WS_URL =
  import.meta.env.VITE_WS_URL ||
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/audio`;

export const EMPTY = {
  connection: "idle", // idle | connecting | open | reconnecting | error
  services: { stt: "standby", gemini: "standby", pgvector: "standby", tts: "standby" },
  finals: [],
  partial: null,
  words: [],
  threat: { score: 0, state: "idle" },
  evidence: [],
  guard: [],
  tools: [],
  kase: null,
  docs: {},
  stats: {},
  error: null,
};

function reduce(state, ev) {
  switch (ev.type) {
    case "connection.status":
      return { ...state, services: { ...state.services, [ev.service]: ev.state } };
    case "transcript.partial":
      return { ...state, partial: ev };
    case "transcript.final":
      return { ...state, finals: [...state.finals, ev], partial: null };
    case "word.ts":
      return { ...state, words: [...state.words, ev] };
    case "threat.update":
      return { ...state, threat: { score: ev.score, state: ev.state } };
    case "evidence.update":
      return { ...state, evidence: ev.signals };
    case "guard.action":
      return { ...state, guard: [...state.guard, ev] };
    case "tool.call":
      return { ...state, tools: [...state.tools, { ...ev, status: "pending" }] };
    case "tool.result":
      return {
        ...state,
        tools: state.tools.map((t) =>
          t.name === ev.name && t.status === "pending"
            ? { ...t, status: "done", ms: ev.ms, result: ev.result }
            : t,
        ),
      };
    case "case.update":
      return { ...state, kase: { ...(state.kase || {}), ...ev } };
    case "doc.ready":
      return { ...state, docs: { ...state.docs, [ev.doc]: ev } };
    case "stat.update":
      return { ...state, stats: { ...state.stats, [ev.key]: ev.value } };
    case "error":
      return { ...state, error: ev.message };
    default:
      return state;
  }
}

export function useSurakshaSocket() {
  const [state, setState] = useState(EMPTY);
  const ws = useRef(null);
  const retry = useRef(0);
  const timer = useRef(null);
  const alive = useRef(true);

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;
    setState((s) => ({ ...s, connection: retry.current ? "reconnecting" : "connecting" }));

    let sock;
    try {
      sock = new WebSocket(WS_URL);
    } catch {
      setState((s) => ({ ...s, connection: "error" }));
      return;
    }
    sock.binaryType = "arraybuffer";
    ws.current = sock;

    sock.onopen = () => {
      retry.current = 0;
      setState((s) => ({ ...s, connection: "open", error: null }));
    };
    sock.onmessage = (e) => {
      let ev;
      try {
        ev = JSON.parse(e.data);
      } catch {
        return;
      }
      setState((s) => reduce(s, ev));
    };
    sock.onerror = () => setState((s) => ({ ...s, connection: "error" }));
    sock.onclose = () => {
      if (!alive.current) return;
      // Backoff caps at 8s so a sleeping Render instance is still picked up
      // quickly once it wakes, without hammering it meanwhile.
      const delay = Math.min(8000, 500 * 2 ** retry.current++);
      setState((s) => ({ ...s, connection: "reconnecting" }));
      timer.current = setTimeout(connect, delay);
    };
  }, []);

  useEffect(() => {
    alive.current = true;
    connect();
    return () => {
      alive.current = false;
      clearTimeout(timer.current);
      ws.current?.close();
      ws.current = null;
    };
  }, [connect]);

  const sendAudio = useCallback((buffer) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(buffer);
  }, []);

  const sendControl = useCallback((msg) => {
    if (ws.current?.readyState === WebSocket.OPEN)
      ws.current.send(JSON.stringify(msg));
  }, []);

  const reset = useCallback(
    () => setState((s) => ({ ...EMPTY, connection: s.connection, services: s.services })),
    [],
  );

  return useMemo(
    () => ({ ...state, sendAudio, sendControl, reset }),
    [state, sendAudio, sendControl, reset],
  );
}
