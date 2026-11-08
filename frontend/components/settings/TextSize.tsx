"use client";

import { useEffect, useState } from "react";
import { cx } from "@/components/ui";

const OPTIONS = [
  { key: "normal", label: "Normal", sample: "text-[1rem]" },
  { key: "large", label: "Large", sample: "text-[1.15rem]" },
  { key: "largest", label: "Largest", sample: "text-[1.3rem]" },
] as const;

type Size = (typeof OPTIONS)[number]["key"];

/** Text size for this device. The whole interface scales with it. */
export function TextSize() {
  const [size, setSize] = useState<Size>("normal");
  useEffect(() => setSize((document.documentElement.dataset.text as Size) || "normal"), []);

  function choose(next: Size) {
    setSize(next);
    const html = document.documentElement;
    if (next === "normal") delete html.dataset.text; else html.dataset.text = next;
    try { if (next === "normal") localStorage.removeItem("ss-text"); else localStorage.setItem("ss-text", next); } catch { /* private mode */ }
  }

  return (
    <div role="radiogroup" aria-label="Text size" className="grid grid-cols-3 gap-3">
      {OPTIONS.map((o) => (
        <button
          key={o.key}
          type="button"
          role="radio"
          aria-checked={size === o.key}
          onClick={() => choose(o.key)}
          className={cx(
            "rounded-xl border-2 px-4 py-4 text-left transition-colors",
            size === o.key ? "border-accent bg-surface-2" : "border-line hover:border-line-strong",
          )}
        >
          <span className={cx("block font-bold leading-none", o.sample)}>Aa</span>
          <span className="block mt-2 text-[0.85rem] text-ink-2">{o.label}</span>
        </button>
      ))}
    </div>
  );
}
