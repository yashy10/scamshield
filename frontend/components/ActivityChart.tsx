"use client";

import { useId, useState, type KeyboardEvent } from "react";
import { dayLabel, fmt } from "@/lib/format";
import type { SeriesPoint } from "@/lib/types";
import { STATUS_COLOR, Swatch } from "./ui";

const KEYS = [
  { key: "scam", label: "Scam", color: STATUS_COLOR.scam },
  { key: "suspicious", label: "Careful look", color: STATUS_COLOR.careful },
  { key: "safe", label: "Safe", color: STATUS_COLOR.safe },
] as const;

function niceMax(n: number): number {
  if (n <= 5) return 5;
  const pow = 10 ** Math.floor(Math.log10(n));
  const steps = [1, 2, 2.5, 5, 10];
  for (const s of steps) if (s * pow >= n) return s * pow;
  return 10 * pow;
}

/**
 * Emails checked per day (or week), stacked by verdict: scam on top so it's never buried under the
 * safe mail. Hover, tap or use the arrow keys to read a column; a table carries the same numbers.
 */
export function ActivityChart({ points, unit }: { points: SeriesPoint[]; unit: "day" | "week" }) {
  const [active, setActive] = useState<number | null>(null);
  const tableId = useId();
  const totals = points.map((p) => p.safe + p.suspicious + p.scam);
  const top = niceMax(Math.max(...totals, 0));
  const ticks = [0, top / 2, top];
  const shown = active ?? points.length - 1;
  const p = points[shown];
  // About eight date labels on wide screens, four on phones; phone labels are a subset, counted back from today.
  const labelEvery = points.length > 16 ? Math.ceil(points.length / 8) : points.length > 8 ? 2 : 1;
  const last = points.length - 1;
  const labelClass = (i: number) =>
    (last - i) % (labelEvery * 2) === 0 ? "" : (last - i) % labelEvery === 0 ? "hidden sm:inline" : null;

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const next = Math.min(points.length - 1, Math.max(0, shown + (e.key === "ArrowRight" ? 1 : -1)));
      setActive(next);
    }
  }

  if (!points.length) return null;

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 px-6">
        <p className="text-ink-2 text-[0.9rem]" aria-live="polite">
          <span className="text-ink font-semibold">{unit === "day" ? dayLabel(p.start, true) : `Week of ${dayLabel(p.start)}`}</span>
          {": "}
          <span className="num">{fmt(totals[shown])}</span> checked
          {p.scam > 0 && <>, <span className="num">{p.scam}</span> scam</>}
          {p.suspicious > 0 && <>, <span className="num">{p.suspicious}</span> to look at carefully</>}
        </p>
        <ul className="flex gap-4 text-[0.8rem] text-muted">
          {KEYS.map((k) => (
            <li key={k.key} className="flex items-center gap-1.5"><Swatch color={k.color} />{k.label}</li>
          ))}
        </ul>
      </div>

      <div className="relative mt-4 px-6 pb-5">
        <div className="absolute left-6 right-6 top-0 bottom-12 pointer-events-none" aria-hidden>
          {ticks.map((t) => (
            <div key={t} className="absolute left-0 right-0 border-t border-line/70" style={{ bottom: `${(t / top) * 100}%` }}>
              <span className="absolute -top-2.5 right-0 bg-surface pl-2 text-[0.7rem] text-muted num">{fmt(t)}</span>
            </div>
          ))}
        </div>
        <div
          role="group"
          aria-label="Emails checked over time. Use the left and right arrow keys to read each column."
          aria-describedby={tableId}
          tabIndex={0}
          onKeyDown={onKey}
          onMouseLeave={() => setActive(null)}
          className="relative flex items-end h-56 pr-9 rounded-md"
        >
          {points.map((pt, i) => {
            const total = totals[i];
            const isActive = i === shown;
            return (
              <div
                key={pt.start}
                className="group relative flex-1 h-full flex flex-col justify-end items-center cursor-default"
                onMouseEnter={() => setActive(i)}
                onClick={() => setActive(i)}
              >
                <div
                  className="flex flex-col gap-[2px] w-[62%] max-w-7 rounded-t-[4px] overflow-hidden transition-[filter] duration-100"
                  style={{ height: `${(total / top) * 100}%`, filter: active !== null && !isActive ? "saturate(0.45) brightness(0.75)" : undefined }}
                >
                  {KEYS.map((k) => pt[k.key] > 0 && (
                    <span key={k.key} style={{ flexGrow: pt[k.key], flexBasis: 0, minHeight: 3, background: k.color }} />
                  ))}
                </div>
                {isActive && active !== null && <div aria-hidden className="absolute inset-y-0 w-full rounded-md bg-surface-3/40 -z-10" />}
              </div>
            );
          })}
        </div>
        <div className="flex pr-9 border-t-2 border-line-strong pt-2" aria-hidden>
          {points.map((pt, i) => (
            <span key={pt.start} className="flex-1 min-w-0 flex justify-center text-[0.7rem] text-muted whitespace-nowrap">
              {labelClass(i) !== null && <span className={labelClass(i) || undefined}>{dayLabel(pt.start)}</span>}
            </span>
          ))}
        </div>
      </div>

      <div className="sr-only">
      <table id={tableId}>
        <caption>Emails checked per {unit}</caption>
        <thead><tr><th scope="col">{unit === "day" ? "Day" : "Week of"}</th><th scope="col">Checked</th><th scope="col">Scam</th><th scope="col">Careful look</th><th scope="col">Safe</th></tr></thead>
        <tbody>
          {points.map((pt, i) => (
            <tr key={pt.start}><th scope="row">{dayLabel(pt.start)}</th><td>{totals[i]}</td><td>{pt.scam}</td><td>{pt.suspicious}</td><td>{pt.safe}</td></tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
