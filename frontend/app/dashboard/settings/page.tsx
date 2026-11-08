import type { Metadata } from "next";
import { ArrowUpRight, Check, X } from "lucide-react";
import { AppShell } from "@/components/shell/AppShell";
import { TextSize } from "@/components/settings/TextSize";
import { Panel } from "@/components/ui";
import { gmailLink } from "@/lib/format";
import { loadDashboard } from "@/lib/load";

export const metadata: Metadata = { title: "Settings" };

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[14rem_1fr] sm:gap-6 py-4 border-b border-line last:border-b-0">
      <dt className="text-ink-2 font-semibold">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

export default async function SettingsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const data = await loadDashboard(typeof sp.person === "string" ? sp.person : undefined, "30");
  const person = data.view?.person;
  const own = person?.role === "self";
  return (
    <AppShell data={data} section="settings" period="30" title="Settings" subtitle="How ScamShield looks and who it tells." showPeriod={false}>
      <div className="grid grid-cols-1 gap-6 max-w-4xl">
        <Panel className="p-6 sm:p-7" aria-labelledby="text-size">
          <h2 id="text-size" className="text-[1.1rem] font-bold">Text size</h2>
          <p className="mt-1 mb-5 text-ink-2">Makes everything in ScamShield bigger on this device.</p>
          <TextSize />
        </Panel>

        {person && (
          <Panel className="p-6 sm:p-7" aria-labelledby="who">
            <h2 id="who" className="text-[1.1rem] font-bold">{own ? "Your protection" : `${person.name}’s protection`}</h2>
            <dl className="mt-3">
              <Row label="Gmail being checked">
                {person.email}
                {own && (
                  <a href={gmailLink(person.email)} target="_blank" rel="noreferrer" className="ml-3 inline-flex items-center gap-1 text-accent font-semibold hover:underline underline-offset-4">
                    ScamShield label <ArrowUpRight aria-hidden className="w-4 h-4" />
                  </a>
                )}
              </Row>
              <Row label="Warnings go to">{own ? "You" : person.name}{person.guardianEmail ? `, with a copy to ${own ? (person.guardianName ? `${person.guardianName} (${person.guardianEmail})` : person.guardianEmail) : "you"}` : ""}</Row>
              <Row label="Signed in as">{data.account.email}</Row>
            </dl>
            <p className="mt-4 text-[0.88rem] text-muted">To change who gets warnings, or to stop ScamShield, contact the person who set it up. Removing ScamShield’s access in your Google account also stops it.</p>
            <a href="https://myaccount.google.com/connections" target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[0.9rem] font-semibold text-accent hover:underline underline-offset-4">
              Google account connections <ArrowUpRight aria-hidden className="w-4 h-4" />
            </a>
          </Panel>
        )}

        <Panel className="p-6 sm:p-7" aria-labelledby="privacy">
          <h2 id="privacy" className="text-[1.1rem] font-bold">Privacy</h2>
          <div className="mt-4 grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="font-semibold text-ink-2">ScamShield does</h3>
              <ul className="mt-2 space-y-2">
                {["Check links in new emails", "Label risky emails in Gmail", "Send a plain warning, with a copy to your family contact", "Keep the sender, subject and date of flagged emails, to show them here"].map((t) => (
                  <li key={t} className="flex gap-2.5"><Check aria-hidden className="w-5 h-5 text-safe-text shrink-0 mt-0.5" />{t}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-semibold text-ink-2">ScamShield never</h3>
              <ul className="mt-2 space-y-2">
                {["Deletes, moves or sends your email", "Stores the text of your emails", "Shows family contacts your emails or subjects", "Asks for your Google password"].map((t) => (
                  <li key={t} className="flex gap-2.5"><X aria-hidden className="w-5 h-5 text-scam-text shrink-0 mt-0.5" />{t}</li>
                ))}
              </ul>
            </div>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
