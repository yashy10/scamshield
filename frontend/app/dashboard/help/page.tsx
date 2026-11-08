import type { Metadata } from "next";
import { ArrowUpRight } from "lucide-react";
import { Checklist } from "@/components/help/Checklist";
import { AppShell } from "@/components/shell/AppShell";
import { Panel } from "@/components/ui";
import { loadDashboard } from "@/lib/load";

export const metadata: Metadata = { title: "If you clicked a link" };

const ext = (href: string, label: string) => (
  <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-accent hover:underline underline-offset-4">
    {label}<ArrowUpRight aria-hidden className="w-4 h-4" />
  </a>
);

const STEPS = [
  { id: "stop", title: "Stop and close the page", body: <p>Don’t type anything else into it, and don’t call any number it shows. Closing the tab is enough.</p> },
  { id: "password", title: "Typed a password? Change it now", body: <p>Change it on the real website, typed in yourself or from your bookmarks, not from a link in the email. If you use the same password anywhere else, change those too.</p> },
  { id: "bank", title: "Gave card or bank details? Call your bank", body: <p>Use the phone number on the back of your card. Ask them to watch for charges you don’t recognize, or to send you a new card.</p> },
  { id: "remote", title: "Let someone onto your computer? Disconnect it", body: <p>Turn off the Wi-Fi or unplug the internet cable, then ask someone you trust to help check the computer before you use it for banking.</p> },
  { id: "report", title: "Report it", body: <><p>Reporting helps stop the same scam reaching other people.</p><p>{ext("https://reportfraud.ftc.gov/", "Report to the FTC")}{"  "}</p><p>If you shared your Social Security number: {ext("https://www.identitytheft.gov/", "IdentityTheft.gov")}</p></> },
];

const SIGNS = [
  "It’s urgent: pay today, your account is locked, your package is on hold.",
  "The sender’s name says one company, but the address after the @ is something else.",
  "It asks for a password, a card number, a gift card or a call to a phone number.",
  "It offers a prize, refund or job you didn’t ask for.",
];

export default async function HelpPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const data = await loadDashboard(typeof sp.person === "string" ? sp.person : undefined, "30");
  return (
    <AppShell data={data} section="help" period="30" title="If you clicked a link" subtitle="Five steps that keep your money and accounts safe." showPeriod={false}>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_22rem] max-w-6xl">
        <div>
          <p className="text-[1.1rem] text-ink-2 max-w-2xl">
            Clicking a link on its own rarely causes harm. What matters is what happened next. Go through these in order and tick each one off.
          </p>
          <div className="mt-6"><Checklist steps={STEPS} storageKey="ss-help-checklist" /></div>
        </div>
        <aside className="space-y-6">
          <Panel className="p-6">
            <h2 className="text-[1.05rem] font-bold">How to spot a scam email</h2>
            <ul className="mt-3 space-y-3 text-ink-2">
              {SIGNS.map((s) => <li key={s} className="flex gap-3"><span aria-hidden className="mt-2 w-1.5 h-1.5 rounded-full bg-careful shrink-0" />{s}</li>)}
            </ul>
          </Panel>
          <Panel className="p-6">
            <h2 className="text-[1.05rem] font-bold">Not sure about an email?</h2>
            <p className="mt-2 text-ink-2">Call the company using a number you already have, never the one in the email. Or ask your family contact to take a look.</p>
          </Panel>
        </aside>
      </div>
    </AppShell>
  );
}
