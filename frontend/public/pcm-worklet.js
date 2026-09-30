/**
 * Mic -> 16kHz PCM16 mono (CLAUDE.MD §7.3).
 *
 * Browsers capture at 44.1/48kHz; AssemblyAI Realtime needs 16kHz. §7.3 says
 * downsample client-side, before WS#1, so that is done here rather than on the
 * backend — it also cuts the bytes on the wire by a third.
 *
 * Output is posted in ~100ms chunks. The API accepts 50-1000ms and returns
 * inconsistent turns outside that, which would corrupt the word timings the
 * forensic record depends on.
 *
 * The `muted` flag is the seam for two separate rules:
 *   §7.2   half-duplex — stop sending while agent TTS plays, or the agent
 *          transcribes its own voice and loops forever.
 *   C1     the guard's predictive channel cut. Muting HERE (before the socket)
 *          is the only place a cut can actually prevent audio leaving. Reacting
 *          to a word timestamp from STT is always too late — that audio is gone.
 */

const TARGET_RATE = 16000;
const CHUNK_MS = 100;

/**
 * Local VAD for the guard's channel cut (§7.1).
 *
 * RMS over the raw input, before any resampling. Gate 0 measured 1042-1125ms
 * from first audio chunk to first STT partial — so anything that waits for a
 * transcript has already lost by a full second. This runs on the audio thread
 * with no network hop at all, which is the only way a cut can precede the
 * speech it is cutting.
 *
 * The threshold is deliberately low. A missed detection leaks an OTP; a false
 * one costs a fraction of a second of muted silence.
 */
const VAD_RMS_THRESHOLD = 0.012;
const VAD_RELEASE_MS = 600;

class PcmDownsampler extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.targetRate = options?.processorOptions?.targetRate ?? TARGET_RATE;
    this.ratio = sampleRate / this.targetRate;
    this.pos = 0;
    this.tail = new Float32Array(0);
    this.chunkSamples = Math.round((this.targetRate * CHUNK_MS) / 1000);
    this.buf = new Int16Array(this.chunkSamples);
    this.n = 0;
    this.muted = false;

    // Set by the backend when the guard reaches "critical". Until then VAD is
    // measured but never acts — the mic must keep working during a normal call.
    this.armed = false;
    this.speaking = false;
    this.lastVoiceAt = 0;

    this.port.onmessage = (e) => {
      const d = e.data || {};
      if (d.type === "mute") this.muted = !!d.value;
      if (d.type === "arm") this.armed = !!d.value;
    };
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    this.detectVoice(channel);

    // Keep resampling while muted so the fractional read position stays
    // aligned; simply drop the output. Skipping outright would make audio
    // jump on unmute.
    const src = new Float32Array(this.tail.length + channel.length);
    src.set(this.tail);
    src.set(channel, this.tail.length);

    let p = this.pos;
    while (Math.floor(p) + 1 < src.length) {
      const i = Math.floor(p);
      const frac = p - i;
      const s = src[i] * (1 - frac) + src[i + 1] * frac;
      const c = Math.max(-1, Math.min(1, s));
      this.buf[this.n++] = c < 0 ? c * 0x8000 : c * 0x7fff;

      if (this.n === this.chunkSamples) {
        if (!this.muted) this.port.postMessage(this.buf.slice().buffer);
        this.n = 0;
      }
      p += this.ratio;
    }

    const consumed = Math.floor(p);
    this.tail = src.slice(consumed);
    this.pos = p - consumed;
    return true;
  }

  /**
   * The cut itself. When armed and the victim starts speaking, `muted` is set
   * HERE, on the audio thread, in the same render quantum — the frames are
   * never handed to postMessage, so nothing reaches the socket. The main
   * thread is only notified afterwards so the UI and the forensic record can
   * catch up; it is told what happened, it does not authorise it.
   */
  detectVoice(channel) {
    let sum = 0;
    for (let i = 0; i < channel.length; i++) sum += channel[i] * channel[i];
    const rms = Math.sqrt(sum / channel.length);
    const now = (currentFrame / sampleRate) * 1000;

    if (rms > VAD_RMS_THRESHOLD) {
      this.lastVoiceAt = now;
      if (!this.speaking) {
        this.speaking = true;
        if (this.armed) this.muted = true;
        this.port.postMessage({ type: "vad", speaking: true });
      }
    } else if (this.speaking && now - this.lastVoiceAt > VAD_RELEASE_MS) {
      this.speaking = false;
      this.port.postMessage({ type: "vad", speaking: false });
    }
  }
}

registerProcessor("pcm-downsampler", PcmDownsampler);
