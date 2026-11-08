"use client";

import { Check } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { cx } from "@/components/ui";

export interface ChecklistStep {
  id: string;
  title: string;
  body: ReactNode;
}

/** Steps you can tick off as you go. Ticks stay on this device only. */
export function Checklist({ steps, storageKey }: { steps: ChecklistStep[]; storageKey: string }) {
  const [done, setDone] = useState<string[]>([]);
  useEffect(() => {
    try { setDone(JSON.parse(localStorage.getItem(storageKey) ?? "[]")); } catch { /* private mode */ }
  }, [storageKey]);

  function toggle(id: string) {
    const next = done.includes(id) ? done.filter((d) => d !== id) : [...done, id];
    setDone(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* private mode */ }
  }

  return (
    <>
      <p className="text-[0.85rem] text-muted" aria-live="polite">{done.length} of {steps.length} done</p>
      <ol className="mt-3 space-y-3">
        {steps.map((s, i) => {
          const isDone = done.includes(s.id);
          return (
            <li key={s.id} className={cx("rounded-2xl border p-5 transition-colors", isDone ? "border-line bg-surface/60" : "border-line-strong bg-surface")}>
              <div className="flex gap-4">
                <button
                  type="button"
                  onClick={() => toggle(s.id)}
                  aria-pressed={isDone}
                  aria-label={`${isDone ? "Mark not done" : "Mark done"}: ${s.title}`}
                  className={cx(
                    "grid place-items-center w-9 h-9 rounded-full border-2 shrink-0 font-bold transition-colors",
                    isDone ? "bg-safe border-safe text-bg" : "border-line-strong text-ink-2 hover:border-accent",
                  )}
                >
                  {isDone ? <Check aria-hidden className="w-5 h-5" strokeWidth={3} /> : i + 1}
                </button>
                <div className="min-w-0">
                  <h3 className={cx("text-[1.1rem] font-bold", isDone && "text-ink-2")}>{s.title}</h3>
                  <div className="mt-1 text-ink-2 space-y-2">{s.body}</div>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </>
  );
}
