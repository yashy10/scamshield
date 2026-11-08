import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Sparkline } from "@/components/Sparkline";
import { Panel, cx } from "@/components/ui";
import { delta, fmt } from "@/lib/format";
import type { InboxView } from "@/lib/types";

type Good = "up" | "down" | "neither";

function Delta({ now, before, good }: { now: number; before?: number; good: Good }) {
  const d = delta(now, before);
  if (!d) return <p className="text-[0.78rem] text-muted">Since checks began</p>;
  const tone = d.dir === "flat" || good === "neither" ? "text-muted" : (d.dir === good ? "text-safe-text" : "text-scam-text");
  const Icon = d.dir === "up" ? ArrowUpRight : d.dir === "down" ? ArrowDownRight : Minus;
  return (
    <p className={cx("inline-flex items-center gap-1 text-[0.78rem] font-semibold", tone)}>
      <Icon aria-hidden className="w-3.5 h-3.5" />
      <span className="num">{d.text}</span>
    </p>
  );
}

/** Four headline numbers in one panel, each with its trend over the period and the change from the one before. */
export function KpiPanel({ view }: { view: InboxView }) {
  const pts = view.series.points;
  const prev = view.previous ?? undefined;
  const warned = [view.person.role === "self" ? "you" : view.person.name, view.person.guardianName && (view.person.role === "guardian" ? "you" : view.person.guardianName)]
    .filter(Boolean).join(" and ");
  const items = [
    { label: "Emails checked", value: view.counts.checked, series: pts.map((p) => p.safe + p.suspicious + p.scam), before: prev?.checked, good: "neither" as Good },
    { label: "Scams caught", value: view.counts.scam, series: pts.map((p) => p.scam), before: prev?.scam, good: "down" as Good },
    { label: "Needed a careful look", value: view.counts.suspicious, series: pts.map((p) => p.suspicious), before: prev?.suspicious, good: "down" as Good },
    { label: "Warnings sent", value: view.counts.warningsSent, series: null, before: undefined, good: "neither" as Good },
  ];
  return (
    <Panel aria-label="Headline numbers" className="grid grid-cols-2 lg:grid-cols-4 overflow-hidden">
      {items.map((it, i) => (
        <div
          key={it.label}
          className={cx(
            "flex flex-col justify-between gap-3 p-5 sm:p-6 min-h-[9.5rem] border-line",
            i % 2 === 0 && "border-r", i < 2 && "border-b lg:border-b-0", i === 1 && "lg:border-r", i === 2 && "lg:border-r",
          )}
        >
          <p className="text-[0.85rem] text-ink-2 font-semibold">{it.label}</p>
          <div className="flex items-end justify-between gap-3">
            <p className="text-[2.1rem] sm:text-[2.4rem] font-extrabold leading-none num">{fmt(it.value)}</p>
            {it.series && <div className="hidden sm:block"><Sparkline values={it.series} width={110} height={34} /></div>}
          </div>
          {it.series ? <Delta now={it.value} before={it.before} good={it.good} /> : (
            <p className="text-[0.78rem] text-muted">To {warned || "the person"}</p>
          )}
        </div>
      ))}
    </Panel>
  );
}
