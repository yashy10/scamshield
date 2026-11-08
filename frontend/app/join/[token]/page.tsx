import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Check, X } from "lucide-react";
import { Frame } from "@/components/onboarding/Frame";
import { Button, VerdictPill } from "@/components/ui";
import { getInvite } from "@/lib/api";

export const metadata: Metadata = { title: "Connect your Gmail" };

export default async function JoinPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const invite = await getInvite(token);
  if (!invite) notFound();
  if (invite.connected) redirect(`/protected/${token}`);
  const { protectedName: name, guardianName: guardian } = invite;
  return (
    <Frame wide>
      <h1 className="text-[2.1rem] sm:text-[2.5rem] font-extrabold leading-tight">Hi {name}. {guardian} set up ScamShield for you.</h1>
      <p className="mt-4 text-ink-2 text-[1.12rem] max-w-2xl">
        ScamShield looks at the links in your new emails. If one looks like a scam, it adds a label in Gmail and sends you a short warning, like the one below.
      </p>

      <div className="mt-8 grid gap-8 sm:grid-cols-2">
        <div>
          <h2 className="font-bold text-[1.1rem]">What it does</h2>
          <ul className="mt-3 space-y-2.5">
            {["Checks each link in new emails.", "Labels risky emails “ScamShield” in Gmail.", `Sends you a warning, with a copy to ${guardian}.`].map((t) => (
              <li key={t} className="flex gap-3"><Check aria-hidden className="w-5 h-5 mt-0.5 text-safe-text shrink-0" strokeWidth={3} />{t}</li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="font-bold text-[1.1rem]">What it never does</h2>
          <ul className="mt-3 space-y-2.5">
            {["Delete, move or send your email.", `Show ${guardian} your emails. ${guardian} sees warnings only.`, "Ask for your password. You sign in on Google’s own page."].map((t) => (
              <li key={t} className="flex gap-3"><X aria-hidden className="w-5 h-5 mt-0.5 text-scam-text shrink-0" strokeWidth={3} />{t}</li>
            ))}
          </ul>
        </div>
      </div>

      <figure className="mt-9 rounded-2xl border border-line bg-surface-2 overflow-hidden" aria-label="A sample warning">
        <div className="border-b border-line px-5 py-3 text-[0.88rem] text-muted">
          <p><span className="inline-block w-16">From</span><span className="text-ink-2">ScamShield</span></p>
          <p><span className="inline-block w-16">Subject</span><span className="text-ink-2">ScamShield: likely scam in your inbox</span></p>
        </div>
        <div className="px-5 py-4">
          <VerdictPill verdict="scam" />
          <p className="mt-3 font-bold text-[1.1rem]">This email is likely a scam. Don’t click its links.</p>
          <p className="mt-1 text-ink-2">The email titled “Your account has been locked”, from chase-secure-login[.]com.</p>
          <p className="mt-3 font-semibold">Why:</p>
          <ul className="mt-1 space-y-1 text-ink-2 list-disc pl-5">
            <li>The website was registered 3 days ago.</li>
            <li>Google Safe Browsing lists the link as phishing.</li>
          </ul>
        </div>
      </figure>

      <form method="post" action={`/join/${encodeURIComponent(token)}/connect`} className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button type="submit" size="lg">Connect my Gmail</Button>
        <p className="text-[0.9rem] text-muted">Google will show its own page and ask you to allow ScamShield.</p>
      </form>
    </Frame>
  );
}
