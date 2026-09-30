/**
 * Agent voice playback + the §7.3 half-duplex rule.
 *
 * The rule exists because without it the agent transcribes its own voice
 * through the mic and talks to itself forever. So while a clip plays the mic
 * stops sending, and it resumes 300ms after playback ends — long enough for
 * the tail of the speaker output to die away in a room with open speakers.
 *
 * Clips are queued rather than overlapped. The agent often emits a refusal and
 * a follow-up question in the same turn, and two voices talking over each
 * other is worse than a half-second gap.
 */

import { useCallback, useEffect, useRef, useState } from "react";

/** §7.3. Measured from the audio element's 'ended' event. */
const RESUME_DELAY_MS = 300;

export function useTts(setMuted) {
  const [speaking, setSpeaking] = useState(false);
  const [blocked, setBlocked] = useState(false);

  const audio = useRef(null);
  const queue = useRef([]);
  const playing = useRef(false);
  const resumeTimer = useRef(null);

  if (audio.current === null && typeof Audio !== "undefined") {
    audio.current = new Audio();
    audio.current.preload = "auto";
  }

  const drain = useCallback(async () => {
    if (playing.current) return;

    const next = queue.current.shift();
    if (next === undefined) {
      // Queue empty: release the mic after the grace period. Cancel any
      // pending release first, or a clip that started during the wait would
      // un-mute mid-sentence.
      clearTimeout(resumeTimer.current);
      resumeTimer.current = setTimeout(() => {
        setMuted?.(false);
        setSpeaking(false);
      }, RESUME_DELAY_MS);
      return;
    }

    clearTimeout(resumeTimer.current);
    playing.current = true;
    setSpeaking(true);
    setMuted?.(true);

    const el = audio.current;
    el.src = next;
    try {
      await el.play();
    } catch (err) {
      // Autoplay is blocked until the page has been interacted with. The
      // conversation must continue silently rather than stall — the agent's
      // words are already on screen as transcript.final.
      if (err?.name === "NotAllowedError") setBlocked(true);
      playing.current = false;
      drain();
      return;
    }

    el.onended = el.onerror = () => {
      playing.current = false;
      drain();
    };
  }, [setMuted]);

  /** Enqueue a clip. Called for every tts.play event. */
  const play = useCallback(
    (url) => {
      if (!url) return;
      queue.current.push(url);
      drain();
    },
    [drain],
  );

  /** Drop everything pending — used when a session is reset. */
  const stop = useCallback(() => {
    queue.current = [];
    clearTimeout(resumeTimer.current);
    const el = audio.current;
    if (el) {
      el.onended = el.onerror = null;
      el.pause();
      el.removeAttribute("src");
    }
    playing.current = false;
    setSpeaking(false);
    setMuted?.(false);
  }, [setMuted]);

  useEffect(() => () => stop(), [stop]);

  return { speaking, blocked, play, stop };
}
