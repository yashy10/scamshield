import type { Metadata } from "next";
import { Frame } from "@/components/onboarding/Frame";
import { ButtonLink, StatusBadge } from "@/components/ui";

export const metadata: Metadata = { title: "Gmail isn’t connected yet" };

const PROBLEMS: Record<string, [string, string]> = {
  restart: ["Start again from your invite link", "This connection didn’t start in this browser, or it expired. Open your invite link and choose Connect my Gmail again."],
  bad_invite: ["That invite link doesn’t work", "Ask the person who sent it for a new invite link."],
  not_connected: ["Gmail isn’t connected yet", "Google sign-in was cancelled, or it didn’t finish in this browser. Open your invite link to try again."],
  failed: ["Gmail isn’t connected yet", "Google didn’t finish the connection. Open your invite link to try again."],
  unavailable: ["Gmail can’t be connected right now", "Something on our side isn’t ready. Try again in a few minutes."],
};

export default async function ConnectProblem({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const [title, body] = PROBLEMS[typeof sp.error === "string" ? sp.error : ""] ?? ["Gmail isn’t connected yet", "Open your invite link to try again."];
  const token = typeof sp.token === "string" && /^[A-Za-z0-9_-]{8,64}$/.test(sp.token) ? sp.token : null;
  return (
    <Frame>
      <StatusBadge status="careful" size={56} />
      <h1 className="mt-6 text-[2rem] font-extrabold leading-tight">{title}</h1>
      <p className="mt-3 text-ink-2 text-[1.05rem]">{body}</p>
      {token && <ButtonLink href={`/join/${token}`} size="lg" className="mt-8">Open the invite again</ButtonLink>}
    </Frame>
  );
}
