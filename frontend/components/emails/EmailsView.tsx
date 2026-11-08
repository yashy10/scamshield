"use client";

import { ChevronRight, Search, ShieldCheck } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { Panel, VerdictPill, cx } from "@/components/ui";
import { periodPhrase, shortDate } from "@/lib/format";
import type { FlaggedEmail, InboxView } from "@/lib/types";
import { EmailSheet } from "./EmailSheet";

type Filter = "open" | "scam" | "suspicious" | "safe";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "open", label: "To review" },
  { key: "scam", label: "Scams" },
  { key: "suspicious", label: "Careful look" },
  { key: "safe", label: "Marked safe" },
];

function matches(f: FlaggedEmail, filter: Filter): boolean {
  if (filter === "safe") return !!f.markedSafe;
  if (f.markedSafe) return false;
  return filter === "open" || f.verdict === filter;
}

/** Every flagged email in the period: filter, search, and open one to see the evidence and act on it. */
export function EmailsView({ view, tz }: { view: InboxView; tz?: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [filter, setFilter] = useState<Filter>("open");
  const [query, setQuery] = useState("");
  const selectedId = params.get("email");
  const selected = view.flagged.find((f) => f.id === selectedId) ?? null;

  const counts = useMemo(
    () => Object.fromEntries(FILTERS.map((f) => [f.key, view.flagged.filter((e) => matches(e, f.key)).length])) as Record<Filter, number>,
    [view.flagged],
  );
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return view.flagged.filter((f) => matches(f, filter)).filter((f) =>
      !q || [f.senderName, f.senderDomain, f.subject, ...f.reasons].some((v) => v?.toLowerCase().includes(q)),
    );
  }, [view.flagged, filter, query]);

  function openEmail(id: string | null) {
    const next = new URLSearchParams(params.toString());
    if (id) next.set("email", id); else next.delete("email");
    const qs = next.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
  }

  return (
    <>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div role="tablist" aria-label="Show" className="flex gap-1 overflow-x-auto rounded-xl border border-line bg-surface p-1 w-full lg:w-auto">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              role="tab"
              aria-selected={filter === f.key}
              onClick={() => setFilter(f.key)}
              className={cx(
                "inline-flex items-center gap-2 h-9 px-3.5 rounded-lg text-[0.88rem] font-semibold whitespace-nowrap transition-colors",
                filter === f.key ? "bg-surface-3 text-ink" : "text-ink-2 hover:text-ink",
              )}
            >
              {f.label}
              <span className={cx("num rounded-full px-1.5 text-[0.72rem]", filter === f.key ? "bg-bg/60" : "bg-surface-2")}>{counts[f.key]}</span>
            </button>
          ))}
        </div>
        <label className="relative block lg:w-80">
          <span className="sr-only">Search caught emails</span>
          <Search aria-hidden className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={view.person.role === "self" ? "Search sender, subject or reason" : "Search sender or reason"}
            className="w-full h-11 rounded-xl border border-line bg-surface pl-10 pr-3 text-[0.95rem] placeholder:text-muted focus:border-accent focus:outline-none"
          />
        </label>
      </div>

      {view.person.role === "guardian" && (
        <p className="mt-4 text-[0.85rem] text-muted">You see who sent each email and why it was flagged, not the email itself.</p>
      )}

      <Panel className="mt-4 overflow-hidden">
        {shown.length === 0 ? (
          <div className="flex flex-col items-center text-center gap-3 px-6 py-16">
            <ShieldCheck aria-hidden className="w-10 h-10 text-safe-text" />
            <p className="text-[1.1rem] font-bold">
              {query ? "Nothing matches that search" : filter === "safe" ? "Nothing marked safe" : `Nothing to review ${periodPhrase(view.period)}`}
            </p>
            <p className="text-ink-2 max-w-md">
              {query ? "Try a sender’s name or part of a website address." : "When ScamShield flags an email, it appears here with the reasons it was flagged."}
            </p>
          </div>
        ) : (
          <ul role="list">
            {shown.map((f) => (
              <li key={f.id} className="border-b border-line last:border-b-0">
                <button
                  type="button"
                  onClick={() => openEmail(f.id)}
                  className="group w-full text-left grid grid-cols-[1fr_auto] sm:grid-cols-[7.5rem_1fr_auto] gap-x-4 gap-y-1 px-5 sm:px-6 py-4 hover:bg-surface-2 focus-visible:bg-surface-2 transition-colors"
                >
                  <span className="sm:pt-0.5"><VerdictPill verdict={f.markedSafe ? "safe" : f.verdict} /></span>
                  <span className="min-w-0 col-span-2 sm:col-span-1 row-start-2 sm:row-start-auto">
                    <span className="flex items-baseline gap-2 min-w-0">
                      <span className="font-bold truncate">{f.senderName || f.senderDomain || "Unknown sender"}</span>
                      {f.senderName && f.senderDomain && <span className="text-[0.82rem] text-muted truncate">{f.senderDomain}</span>}
                    </span>
                    {f.subject && <span className="block text-ink-2 truncate">“{f.subject}”</span>}
                    {f.reasons.length > 0 && <span className="block text-[0.85rem] text-muted truncate">{f.reasons.join(" ")}</span>}
                  </span>
                  <span className="flex items-center gap-1 justify-end text-[0.82rem] text-muted whitespace-nowrap row-start-1 col-start-2 sm:col-start-3 sm:pt-0.5">
                    {shortDate(f.receivedAt ?? f.checkedAt, tz)}
                    <ChevronRight aria-hidden className="w-4 h-4 opacity-40 group-hover:opacity-100 transition-opacity" />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <EmailSheet email={selected} view={view} tz={tz} onClose={() => openEmail(null)} />
    </>
  );
}
