import { ArrowUpRight } from "lucide-react";
import { StatusRing } from "@/components/StatusRing";
import { ButtonLink, Panel, STATUS_COLOR, StatusBadge, Swatch, buttonClass } from "@/components/ui";
import { statusCopy } from "@/lib/copy";
import { ago, fmt, gmailLink, plural } from "@/lib/format";
import type { InboxView } from "@/lib/types";

/** The first thing anyone sees: is this inbox safe, and what should I do next? */
export function StatusPanel({ view }: { view: InboxView }) {
  const { person, counts, status, period } = view;
  const copy = statusCopy({ status, role: person.role, name: person.name, scams: counts.scam, careful: counts.suspicious, period });
  const emailsHref = `/dashboard/${person.id}/emails${period === "30" ? "" : `?period=${period}`}`;
  const legend = [
    { label: "Scams caught", value: counts.scam, color: STATUS_COLOR.scam },
    { label: "Needed a careful look", value: counts.suspicious, color: STATUS_COLOR.careful },
    { label: "Looked safe", value: counts.safe, color: STATUS_COLOR.safe },
  ];
  return (
    <Panel className="relative overflow-hidden" aria-labelledby="status-headline">
      <div aria-hidden className="airmail absolute inset-x-0 top-0 h-1.5 opacity-90" />
      <div className="grid grid-cols-1 gap-8 p-6 pt-8 sm:p-8 sm:pt-10 md:grid-cols-[auto_1fr] md:items-center md:gap-x-12 2xl:grid-cols-[auto_minmax(0,1.3fr)_minmax(16rem,1fr)] xl:px-10">
        <div className="justify-self-center md:row-span-2 2xl:row-span-1">
          <StatusRing
            scam={counts.scam}
            suspicious={counts.suspicious}
            safe={counts.safe}
            status={status}
            size={248}
            label={`${copy.word}. ${counts.scam} scams, ${counts.suspicious} to look at carefully, ${counts.safe} safe, out of ${counts.checked} emails checked.`}
          >
            <div className="flex flex-col items-center">
              <StatusBadge status={status} size={52} />
              <p className="mt-3 text-[1.35rem] font-extrabold leading-tight max-w-[9rem]">{copy.word}</p>
              <p className="mt-0.5 text-[0.82rem] text-muted num">{fmt(counts.checked)} checked</p>
            </div>
          </StatusRing>
        </div>

        <div className="min-w-0">
          <h2 id="status-headline" className="text-[1.6rem] sm:text-[2rem] font-extrabold leading-[1.1]">{copy.headline}</h2>
          <p className="mt-3 text-[1.05rem] text-ink-2 max-w-[36rem]">{copy.detail}</p>

          {(status === "scam" || status === "careful") && (
            <div className="mt-5 flex flex-wrap gap-3">
              <ButtonLink href={emailsHref} size="md">
                Review {plural(counts.scam + counts.suspicious, "email", "emails")}
              </ButtonLink>
              {person.role === "self" && (
                <a className={buttonClass("secondary", "md")} href={gmailLink(person.email)} target="_blank" rel="noreferrer">
                  Open the ScamShield label in Gmail <ArrowUpRight aria-hidden className="w-4 h-4" />
                </a>
              )}
            </div>
          )}

        </div>

        <div className="min-w-0 md:col-start-2 2xl:col-start-3">
          <dl className="grid max-w-[30rem]">
            {legend.map((row) => (
              <div key={row.label} className="flex items-center justify-between gap-4 py-2 border-b border-line">
                <dt className="flex items-center gap-2.5 text-ink-2"><Swatch color={row.color} />{row.label}</dt>
                <dd className="font-bold num">{fmt(row.value)}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-[0.82rem] text-muted">
            Last check {ago(view.lastCheckedAt)}.
            {counts.markedSafe > 0 && ` ${plural(counts.markedSafe, "email was", "emails were")} marked safe by hand.`}
          </p>
        </div>
      </div>
    </Panel>
  );
}
