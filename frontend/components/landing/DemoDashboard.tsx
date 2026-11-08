"use client";

import { useState } from "react";
import { StatusRing } from "@/components/StatusRing";
import { STATUS_COLOR, StatusBadge, StatusDot, Swatch, VerdictPill, cx } from "@/components/ui";
import { statusCopy } from "@/lib/copy";
import { fmt } from "@/lib/format";
import type { Status } from "@/lib/types";

interface Persona {
  id: string;
  name: string;
  status: Status;
  counts: { scam: number; suspicious: number; safe: number };
  flagged: { verdict: "scam" | "suspicious"; sender: string; domain: string; reason: string; when: string }[];
}

// Sample data for the preview only. Every name and address here is made up.
const PEOPLE: Persona[] = [
  {
    id: "margaret", name: "Margaret", status: "scam", counts: { scam: 3, suspicious: 2, safe: 210 },
    flagged: [
      { verdict: "scam", sender: "Chase Security Team", domain: "chase-secure-login.com", reason: "The link goes to a website registered 3 days ago.", when: "Fri" },
      { verdict: "suspicious", sender: "Billing Department", domain: "invoice-paynow.com", reason: "It pushes you to pay quickly to avoid a late fee.", when: "Wed" },
    ],
  },
  { id: "robert", name: "Robert", status: "safe", counts: { scam: 0, suspicious: 0, safe: 97 }, flagged: [] },
  {
    id: "june", name: "June", status: "careful", counts: { scam: 0, suspicious: 1, safe: 142 },
    flagged: [
      { verdict: "suspicious", sender: "Medicare Benefits", domain: "medicare-benefit-update.com", reason: "It asks you to confirm your Medicare number.", when: "Thu" },
    ],
  },
];

/** The landing page's product shot, but live: switch people and the ring redraws with their status. */
export function DemoDashboard() {
  const [active, setActive] = useState(PEOPLE[0].id);
  const p = PEOPLE.find((x) => x.id === active)!;
  const checked = p.counts.scam + p.counts.suspicious + p.counts.safe;
  const copy = statusCopy({ status: p.status, role: "guardian", name: p.name, scams: p.counts.scam, careful: p.counts.suspicious, period: "30" });

  return (
    <figure className="relative">
      <div className="rounded-[22px] border border-line-strong bg-raised shadow-[0_40px_120px_-40px_rgba(59,91,219,0.45)] overflow-hidden">
        <div className="airmail h-1.5" aria-hidden />
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 sm:px-5 py-3 sm:py-0 sm:h-14">
          <p className="font-bold text-[0.95rem]">Family overview</p>
          <div role="tablist" aria-label="Sample people" className="flex gap-1 rounded-xl bg-surface p-1 border border-line">
            {PEOPLE.map((x) => (
              <button
                key={x.id}
                role="tab"
                aria-selected={x.id === active}
                onClick={() => setActive(x.id)}
                className={cx(
                  "inline-flex items-center gap-2 h-8 px-3 rounded-lg text-[0.82rem] font-semibold transition-colors",
                  x.id === active ? "bg-surface-3 text-ink" : "text-ink-2 hover:text-ink",
                )}
              >
                <StatusDot status={x.status} />
                {x.name}
              </button>
            ))}
          </div>
        </div>

        <div className="p-5 sm:p-6">
          <div className="grid gap-6 sm:grid-cols-[auto_1fr] sm:items-center">
            <div className="justify-self-center" key={p.id}>
              <StatusRing scam={p.counts.scam} suspicious={p.counts.suspicious} safe={p.counts.safe} status={p.status} size={188} thickness={20} label={`${p.name}: ${copy.word}`}>
                <div className="flex flex-col items-center">
                  <StatusBadge status={p.status} size={40} />
                  <p className="mt-2 font-extrabold text-[1.05rem] leading-tight max-w-[7rem]">{copy.word}</p>
                  <p className="text-[0.72rem] text-muted num">{fmt(checked)} checked</p>
                </div>
              </StatusRing>
            </div>
            <div className="min-w-0">
              <p className="text-[1.25rem] font-extrabold leading-tight">{copy.headline}</p>
              <dl className="mt-4 space-y-1.5 text-[0.88rem]">
                {[["Scams caught", p.counts.scam, STATUS_COLOR.scam], ["Careful look", p.counts.suspicious, STATUS_COLOR.careful], ["Looked safe", p.counts.safe, STATUS_COLOR.safe]].map(([label, value, color]) => (
                  <div key={label as string} className="flex items-center justify-between gap-6 border-b border-line pb-1.5">
                    <dt className="flex items-center gap-2 text-ink-2"><Swatch color={color as string} />{label}</dt>
                    <dd className="font-bold num">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-line bg-surface">
            <p className="px-4 pt-3 pb-1 text-[0.8rem] font-semibold text-muted">Needs your attention</p>
            {p.flagged.length === 0 ? (
              <p className="px-4 pb-4 pt-1 text-[0.9rem] text-ink-2">Nothing to review. {p.name}’s inbox looks safe.</p>
            ) : (
              <ul>
                {p.flagged.map((f) => (
                  <li key={f.sender} className="flex items-start gap-3 px-4 py-3 border-t border-line first:border-t-0">
                    <VerdictPill verdict={f.verdict} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[0.9rem] font-bold truncate">{f.sender} <span className="font-normal text-muted text-[0.78rem]">{f.domain}</span></p>
                      <p className="text-[0.8rem] text-muted truncate">{f.reason}</p>
                    </div>
                    <span className="text-[0.75rem] text-muted">{f.when}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
      <figcaption className="mt-3 text-center text-[0.8rem] text-muted">A live preview with sample data. Switch between people to see each state.</figcaption>
    </figure>
  );
}
