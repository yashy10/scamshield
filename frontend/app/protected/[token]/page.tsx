import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { StatusBadge, ButtonLink } from "@/components/ui";
import { Frame } from "@/components/onboarding/Frame";
import { getInvite } from "@/lib/api";

export const metadata: Metadata = { title: "You’re protected" };

export default async function ProtectedPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const invite = await getInvite(token);
  if (!invite) notFound();
  if (!invite.connected) redirect(`/join/${token}`);
  return (
    <Frame>
      <StatusBadge status="safe" size={64} />
      <h1 className="mt-6 text-[2.1rem] font-extrabold leading-tight">You’re protected, {invite.protectedName}</h1>
      <p className="mt-3 text-ink-2 text-[1.08rem]">
        ScamShield is now checking the links in your new emails. If one looks like a scam, you’ll get a short warning, and {invite.guardianName} gets a copy.
      </p>
      <p className="mt-3 text-ink-2 text-[1.08rem]">You don’t need to do anything else. Your dashboard shows everything ScamShield checks.</p>
      <ButtonLink href="/dashboard" size="lg" className="mt-8">See your dashboard</ButtonLink>
    </Frame>
  );
}
