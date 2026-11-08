import type { CSSProperties, ReactNode } from "react";
import type { Status } from "@/lib/types";
import { STATUS_COLOR } from "./ui";

const R = 100;
const C = 2 * Math.PI * R;
const GAP = 3.5;
const MIN_SHARE = 0.025; // a single scam among a thousand emails still gets a visible arc
const SWEEP_MS = 950;

interface Part {
  key: "scam" | "suspicious" | "safe";
  count: number;
}

const PART_COLOR = { scam: STATUS_COLOR.scam, suspicious: STATUS_COLOR.careful, safe: STATUS_COLOR.safe };

function arcs(parts: Part[]) {
  const total = parts.reduce((n, p) => n + p.count, 0);
  const shown = parts.filter((p) => p.count > 0);
  if (!total) return [];
  const shares = shown.map((p) => Math.max(p.count / total, MIN_SHARE));
  const biggest = shares.indexOf(Math.max(...shares));
  shares[biggest] -= shares.reduce((a, b) => a + b, 0) - 1;
  const gap = shown.length > 1 ? GAP : 0;
  let start = 0;
  return shown.map((p, i) => {
    const length = shares[i] * C;
    const arc = { ...p, dash: Math.max(length - gap, 0.5), offset: -start, startShare: start / C, share: shares[i] };
    start += length;
    return arc;
  });
}

/**
 * The status ring: every email checked in the period, split into scam (red), careful (yellow) and safe
 * (green), clockwise from twelve o'clock. It sweeps in once; the legend beside it carries the exact counts.
 */
export function StatusRing({
  scam, suspicious, safe, status, size = 260, thickness = 22, children, animate = true, label,
}: {
  scam: number; suspicious: number; safe: number; status: Status; size?: number; thickness?: number;
  children?: ReactNode; animate?: boolean; label: string;
}) {
  const segments = arcs([
    { key: "scam", count: scam },
    { key: "suspicious", count: suspicious },
    { key: "safe", count: safe },
  ]);
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={label}>
      <div
        aria-hidden
        className="absolute inset-[8%] rounded-full blur-2xl opacity-60"
        style={{ background: `radial-gradient(circle, color-mix(in oklab, ${STATUS_COLOR[status]} 30%, transparent) 0%, transparent 70%)` }}
      />
      <svg viewBox="0 0 240 240" className="relative w-full h-full -rotate-90" aria-hidden>
        <circle cx="120" cy="120" r={R} fill="none" stroke="var(--color-surface-3)" strokeWidth={thickness} />
        {segments.map((s) => (
          <circle
            key={s.key}
            cx="120"
            cy="120"
            r={R}
            fill="none"
            stroke={PART_COLOR[s.key]}
            strokeWidth={thickness}
            strokeDasharray={`${s.dash.toFixed(2)} ${(C - s.dash).toFixed(2)}`}
            strokeDashoffset={s.offset.toFixed(2)}
            className={animate ? "ring-seg" : undefined}
            style={{
              "--delay": `${Math.round(120 + s.startShare * SWEEP_MS)}ms`,
              animationDuration: `${Math.max(140, Math.round(s.share * SWEEP_MS))}ms`,
              "--c": C.toFixed(2),
            } as CSSProperties}
          />
        ))}
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}
