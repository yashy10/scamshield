"use client";

import { RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/client";
import type { ScanState } from "@/lib/types";
import { cx } from "@/components/ui";

/** Starts a check of the inbox now, then follows it until it finishes and refreshes the page. */
export function ScanButton({ personId, initial }: { personId: string; initial: ScanState }) {
  const router = useRouter();
  const [state, setState] = useState<ScanState>(initial);
  const [note, setNote] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const busy = state.status === "running" || state.status === "started";

  useEffect(() => setState(initial), [initial]);
  useEffect(() => {
    if (!note) return;
    const id = window.setTimeout(() => setNote(null), 7000);
    return () => window.clearTimeout(id);
  }, [note]);
  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);

  function follow() {
    if (timer.current) window.clearInterval(timer.current);
    const startedAt = Date.now();
    timer.current = window.setInterval(async () => {
      const next = await apiGet<ScanState>(`/api/people/${personId}/scan`);
      if (!next) return;
      setState(next);
      if (next.status === "done" || next.status === "error" || Date.now() - startedAt > 10 * 60_000) {
        if (timer.current) window.clearInterval(timer.current);
        setNote(next.status === "error" ? next.message ?? "The check didn’t finish." : "Check finished.");
        router.refresh();
      }
    }, 4000);
  }

  async function start() {
    setNote(null);
    const res = await apiPost<{ status?: ScanState["status"]; error?: string }>(`/api/people/${personId}/scan`);
    if (!res.ok) {
      setNote(res.data?.error ?? "The check couldn’t start. Try again in a minute.");
      return;
    }
    setState({ status: res.data?.status ?? "running", message: null });
    if (res.data?.status === "started") {
      setNote("Check started. Results appear here in a few minutes.");
      router.refresh();
    } else {
      follow();
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={start}
        disabled={busy}
        className={cx(
          "inline-flex items-center gap-2 h-10 px-3 sm:px-4 rounded-xl border text-[0.85rem] font-semibold transition-colors",
          busy ? "border-line text-muted" : "border-line-strong bg-surface-2 hover:bg-surface-3 text-ink",
        )}
      >
        <RefreshCw aria-hidden className={cx("w-4 h-4", busy && "animate-spin")} />
        <span className="hidden sm:inline">{busy ? "Checking…" : "Check now"}</span>
        <span className="sr-only sm:hidden">{busy ? "Checking the inbox" : "Check the inbox now"}</span>
      </button>
      <p role="status" aria-live="polite" className={cx(
        "absolute right-0 top-12 w-64 rounded-xl border border-line bg-surface-2 px-3 py-2 text-[0.8rem] shadow-xl",
        note ? "block" : "hidden",
      )}>
        {note}
      </p>
    </div>
  );
}
