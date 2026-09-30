/**
 * Microphone capture -> AudioWorklet -> WS#1.
 *
 * The approved mockup had a real bug here: it created the AudioContext in a
 * local `const ctx` but tried to close `window._ac`, which was never assigned.
 * Contexts were therefore never closed, and browsers cap concurrent contexts
 * at roughly six — so the sixth mic test of a demo would silently fail. Every
 * resource created below is tracked in a ref and released in stop().
 */

import { useCallback, useEffect, useRef, useState } from "react";

const BANDS = 40;

export function useMic(sendAudio, onVad) {
  const [active, setActive] = useState(false);
  const [error, setError] = useState(null);
  const [levels, setLevels] = useState(() => new Array(BANDS).fill(0));

  // Held in a ref so a changing callback does not force the mic to restart
  // mid-call, which would drop the stream and re-prompt for permission.
  const onVadRef = useRef(onVad);
  onVadRef.current = onVad;

  const ctx = useRef(null);
  const stream = useRef(null);
  const node = useRef(null);
  const analyser = useRef(null);
  const raf = useRef(null);

  const stop = useCallback(() => {
    cancelAnimationFrame(raf.current);
    raf.current = null;

    node.current?.port?.close?.();
    node.current?.disconnect();
    node.current = null;

    analyser.current?.disconnect();
    analyser.current = null;

    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;

    // The fix: actually close the context we created.
    if (ctx.current && ctx.current.state !== "closed") ctx.current.close();
    ctx.current = null;

    setLevels(new Array(BANDS).fill(0));
    setActive(false);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      stream.current = media;

      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      ctx.current = audioCtx;
      await audioCtx.audioWorklet.addModule("/pcm-worklet.js");

      const source = audioCtx.createMediaStreamSource(media);

      // Spectrum is a real analyser on the raw mic, not an animation.
      const an = audioCtx.createAnalyser();
      an.fftSize = 128;
      analyser.current = an;
      source.connect(an);

      const worklet = new AudioWorkletNode(audioCtx, "pcm-downsampler", {
        processorOptions: { targetRate: 16000 },
      });
      // The worklet posts two things: raw ArrayBuffers of PCM, and VAD
      // notices. Discriminating here keeps a {type:"vad"} object from being
      // sent down the socket as if it were audio.
      worklet.port.onmessage = (e) => {
        if (e.data instanceof ArrayBuffer) sendAudio(e.data);
        else if (e.data?.type === "vad") onVadRef.current?.(e.data.speaking);
      };
      source.connect(worklet);
      node.current = worklet;

      const bins = new Uint8Array(an.frequencyBinCount);
      const tick = () => {
        an.getByteFrequencyData(bins);
        setLevels(Array.from({ length: BANDS }, (_, i) => (bins[i] || 0) / 255));
        raf.current = requestAnimationFrame(tick);
      };
      raf.current = requestAnimationFrame(tick);

      setActive(true);
    } catch (err) {
      setError(
        err?.name === "NotAllowedError"
          ? "Microphone permission denied — allow mic access to run the live test."
          : `Could not start microphone: ${err?.message || err}`,
      );
      stop();
    }
  }, [sendAudio, stop]);

  /** §7.3 half-duplex: hold the mic while agent TTS plays. */
  const setMuted = useCallback((value) => {
    node.current?.port.postMessage({ type: "mute", value });
  }, []);

  /**
   * §7.1: arm the channel cut. Once armed the worklet mutes ITSELF on local
   * VAD, on the audio thread, without asking. Gate 0 measured ~1.1s to the
   * first STT partial, so any round trip through here would be far too late.
   */
  const setArmed = useCallback((value) => {
    node.current?.port.postMessage({ type: "arm", value });
  }, []);

  useEffect(() => stop, [stop]);

  return { active, error, levels, start, stop, setMuted, setArmed };
}
