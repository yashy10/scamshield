import Link from "next/link";
import { ArrowUpRight, LifeBuoy, Mail } from "lucide-react";
import { Panel } from "@/components/ui";
import { gmailLink } from "@/lib/format";
import type { InboxView } from "@/lib/types";

/** What to do next, and who else gets the warnings. */
export function QuickHelp({ view }: { view: InboxView }) {
  const own = view.person.role === "self";
  const helpHref = `/dashboard/help?person=${view.person.id}`;
  return (
    <Panel className="p-6 flex flex-col gap-5" aria-labelledby="quick-help-title">
      <div className="flex items-start gap-3">
        <LifeBuoy aria-hidden className="w-6 h-6 text-accent shrink-0 mt-0.5" />
        <div>
          <h2 id="quick-help-title" className="text-[1.05rem] font-bold">Clicked a link by mistake?</h2>
          <p className="mt-1 text-ink-2 text-[0.95rem]">Don’t panic. Five short steps keep your money and accounts safe.</p>
          <Link href={helpHref} className="mt-3 inline-flex items-center gap-1 font-semibold text-accent hover:underline underline-offset-4">
            Show me what to do
          </Link>
        </div>
      </div>
      <div className="border-t border-line pt-5 flex items-start gap-3">
        <Mail aria-hidden className="w-6 h-6 text-muted shrink-0 mt-0.5" />
        <div className="text-[0.92rem] text-ink-2">
          <p>
            Warnings go to <strong className="text-ink">{own ? "you" : view.person.name}</strong>
            {view.person.guardianEmail && <> with a copy to <strong className="text-ink">{own ? (view.person.guardianName || view.person.guardianEmail) : "you"}</strong></>}.
          </p>
          <p className="mt-1 text-muted text-[0.85rem]">ScamShield never deletes, moves or sends email{own ? "" : `, and you never see ${view.person.name}’s emails`}.</p>
          {own && (
            <a href={gmailLink(view.person.email)} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 font-semibold text-accent hover:underline underline-offset-4">
              See flagged emails in Gmail <ArrowUpRight aria-hidden className="w-4 h-4" />
            </a>
          )}
        </div>
      </div>
    </Panel>
  );
}
