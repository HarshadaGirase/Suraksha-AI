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

    this.port.onmessage = (e) => {
      if (e.data?.type === "mute") this.muted = !!e.data.value;
    };
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

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
}

registerProcessor("pcm-downsampler", PcmDownsampler);
