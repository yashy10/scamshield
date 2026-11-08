import Link from "next/link";
import { ChevronRight, ShieldCheck } from "lucide-react";
import { Panel, PanelHeader, VerdictPill } from "@/components/ui";
import { periodPhrase, shortDate } from "@/lib/format";
import type { InboxView } from "@/lib/types";

/** The latest flagged emails, each one click from its evidence. */
export function AttentionList({ view, tz }: { view: InboxView; tz?: string }) {
  const open = view.flagged.filter((f) => !f.markedSafe);
  const q = view.period === "30" ? "?" : `?period=${view.period}&`;
  const base = `/dashboard/${view.person.id}/emails`;
  return (
    <Panel aria-labelledby="attention-title">
      <PanelHeader
        id="attention-title"
        title="Needs your attention"
        aside={open.length > 0 && <Link href={`${base}${q.slice(0, -1)}`} className="text-[0.85rem] font-semibold text-accent hover:underline underline-offset-4">See all {open.length}</Link>}
      />
      {open.length === 0 ? (
        <div className="flex items-center gap-4 px-6 pb-6 pt-1">
          <ShieldCheck aria-hidden className="w-9 h-9 text-safe-text shrink-0" />
          <p className="text-ink-2">Nothing to review {periodPhrase(view.period)}. When ScamShield flags an email, it shows up here with the reasons.</p>
        </div>
      ) : (
        <ul className="px-3 pb-3">
          {open.slice(0, 4).map((f) => (
            <li key={f.id}>
              <Link
                href={`${base}${q}email=${encodeURIComponent(f.id)}`}
                className="group grid grid-cols-[1fr_auto] sm:grid-cols-[6.75rem_minmax(0,1fr)_auto] items-start gap-x-4 gap-y-1.5 rounded-xl px-3 py-3.5 hover:bg-surface-2 transition-colors"
              >
                <span className="sm:pt-0.5"><VerdictPill verdict={f.verdict} /></span>
                <span className="min-w-0 col-span-2 row-start-2 sm:col-span-1 sm:row-start-auto">
                  <span className="flex flex-wrap items-baseline gap-x-2 min-w-0">
                    <span className="font-bold truncate max-w-full">{f.senderName || f.senderDomain || "Unknown sender"}</span>
                    {f.senderName && f.senderDomain && <span className="text-[0.82rem] text-muted truncate max-w-full">{f.senderDomain}</span>}
                  </span>
                  {f.subject && <span className="block text-ink-2 truncate">“{f.subject}”</span>}
                  {f.reasons[0] && <span className="block text-[0.85rem] text-muted line-clamp-2 sm:line-clamp-1">{f.reasons[0]}</span>}
                </span>
                <span className="col-start-2 row-start-1 sm:col-start-3 flex items-center gap-1 text-[0.8rem] text-muted whitespace-nowrap sm:pt-0.5">
                  {shortDate(f.receivedAt ?? f.checkedAt, tz)}
                  <ChevronRight aria-hidden className="w-4 h-4 opacity-50 group-hover:opacity-100 group-hover:translate-x-0.5 transition" />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
