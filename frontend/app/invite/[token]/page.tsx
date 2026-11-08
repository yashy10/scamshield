import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Mail } from "lucide-react";
import { CopyLink } from "@/components/onboarding/CopyLink";
import { Frame } from "@/components/onboarding/Frame";
import { ButtonLink, buttonClass } from "@/components/ui";
import { getInvite } from "@/lib/api";

export const metadata: Metadata = { title: "Send the invite" };

export default async function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const invite = await getInvite(token);
  if (!invite) notFound();
  const name = invite.protectedName;
  if (invite.connected) {
    return (
      <Frame>
        <h1 className="text-[2rem] font-extrabold leading-tight">{name} is protected</h1>
        <p className="mt-3 text-ink-2 text-[1.05rem]">They connected their Gmail. Sign in with {invite.guardianName}’s email to see their dashboard.</p>
        <ButtonLink href="/dashboard" size="lg" className="mt-7">Open the dashboard</ButtonLink>
      </Frame>
    );
  }
  const subject = encodeURIComponent("I set up ScamShield for you");
  const body = encodeURIComponent(
    `Hi ${name},\n\nI set up ScamShield to help spot scam emails in your Gmail. Open this link and press "Connect my Gmail". You'll sign in on Google's own page:\n\n${invite.inviteUrl}\n\n${invite.guardianName}`,
  );
  return (
    <Frame>
      <h1 className="text-[2rem] font-extrabold leading-tight">Send this link to {name}</h1>
      <p className="mt-3 text-ink-2 text-[1.05rem]">
        When {name} opens it, they’ll read what ScamShield does and connect their own Gmail. Doing it together, on a call or side by side, works best.
      </p>
      <div className="mt-7"><CopyLink url={invite.inviteUrl} label={`Invite link for ${name}`} /></div>
      <a href={`mailto:?subject=${subject}&body=${body}`} className={buttonClass("secondary", "md", "mt-3")}>
        <Mail aria-hidden className="w-4 h-4" /> Email it to them
      </a>
      <ol className="mt-9 space-y-4 border-t border-line pt-7">
        {[
          `${name} opens the link and reads what ScamShield does and never does.`,
          "They choose Connect my Gmail and sign in on Google’s own page.",
          `You both see ${name}’s dashboard. You get a copy of every warning.`,
        ].map((t, i) => (
          <li key={t} className="flex gap-4">
            <span className="grid place-items-center w-8 h-8 rounded-full border border-line-strong text-accent font-bold shrink-0 num">{i + 1}</span>
            <p className="pt-1 text-ink-2">{t}</p>
          </li>
        ))}
      </ol>
    </Frame>
  );
}
