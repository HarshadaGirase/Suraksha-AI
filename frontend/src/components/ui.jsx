/**
 * Shared primitives.
 *
 * The mockup used <div onclick> for tabs and buttons, which cannot be reached
 * by keyboard and announces nothing to a screen reader. Everything interactive
 * here is a real <button>.
 */

export function Card({ className = "", children, ...rest }) {
  return (
    <div
      className={`rounded-xl border border-line bg-panel p-[18px] ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function SecTitle({ children }) {
  return (
    <div className="mb-3 text-[10.5px] font-bold tracking-[2.5px] text-faint">
      {children}
    </div>
  );
}

/** Dashed empty state — §16 BLANK-STATE POLICY. */
export function Empty({ icon, children, className = "" }) {
  return (
    <div
      className={`rounded-[10px] border border-dashed border-line px-4 py-8 text-center text-[11.5px] leading-[1.9] text-faint ${className}`}
    >
      {icon ? <span className="mb-2 block text-[22px] opacity-60">{icon}</span> : null}
      {children}
    </div>
  );
}

const BADGE_TONES = {
  standby: "border-line text-faint",
  online: "border-mint/40 bg-mint/10 text-mint",
  active: "border-violet/40 bg-violet/15 text-[#C4B0FF]",
  armed: "border-amber/40 bg-amber/15 text-amber",
  error: "border-danger/40 bg-danger/15 text-danger",
};

export function Badge({ tone = "standby", children }) {
  return (
    <span
      className={`rounded-[9px] border px-2 py-[2px] text-[8.5px] font-extrabold tracking-[1px] ${
        BADGE_TONES[tone] || BADGE_TONES.standby
      }`}
    >
      {children}
    </span>
  );
}

export function Tab({ active, children, ...rest }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      className={`cursor-pointer rounded-lg border px-[17px] py-[10px] text-xs font-bold tracking-[.5px] transition ${
        active
          ? "border-amber bg-amber/15 text-amber"
          : "border-line bg-panel text-muted hover:text-ink"
      }`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Mini({ children, className = "", ...rest }) {
  return (
    <button
      type="button"
      className={`cursor-pointer rounded-[7px] border border-line bg-panel px-[13px] py-[7px] text-[10.5px] text-muted hover:text-ink disabled:cursor-not-allowed disabled:opacity-45 ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function BigButton({ children, className = "", ...rest }) {
  return (
    <button
      type="button"
      className={`w-full cursor-pointer rounded-[10px] border-none px-4 py-[15px] font-display text-[14.5px] font-extrabold tracking-[1px] transition disabled:cursor-not-allowed disabled:opacity-45 disabled:grayscale ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

/** §18 honesty chip — labels the genuinely simulated parts. */
export function SimChip() {
  return (
    <span className="ml-2 rounded-md border border-amber/35 bg-amber/15 px-[7px] py-[2px] align-middle text-[8.5px] font-extrabold tracking-[1px] text-amber">
      SIM
    </span>
  );
}
