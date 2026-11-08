"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

export function CopyLink({ url, label }: { url: string; label: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch { /* clipboard blocked: the field is selectable */ }
  }
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <input
        readOnly value={url} aria-label={label} onFocus={(e) => e.currentTarget.select()}
        className="min-w-0 flex-1 h-12 rounded-xl border border-line-strong bg-surface-2 px-4 text-[0.92rem] text-ink-2 focus:outline-none focus:border-accent"
      />
      <button type="button" onClick={copy} className="inline-flex items-center justify-center gap-2 h-12 px-5 rounded-xl bg-primary hover:bg-primary-hover font-semibold text-white">
        {copied ? <><Check aria-hidden className="w-4 h-4" /> Copied</> : <><Copy aria-hidden className="w-4 h-4" /> Copy link</>}
      </button>
      <span role="status" aria-live="polite" className="sr-only">{copied ? "Link copied" : ""}</span>
    </div>
  );
}
