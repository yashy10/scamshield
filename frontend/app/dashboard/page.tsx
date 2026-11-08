import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { MailPlus } from "lucide-react";
import { Logo } from "@/components/Logo";
import { ButtonLink, Panel } from "@/components/ui";
import { loadDashboard } from "@/lib/load";

export const metadata: Metadata = { title: "Dashboard" };

/** Sends people to the first inbox they can see, or explains what's missing. */
export default async function DashboardHome() {
  const data = await loadDashboard(undefined, "30");
  if (data.view) redirect(`/dashboard/${data.view.person.id}`);
  return (
    <div className="min-h-dvh flex flex-col">
      <header className="flex items-center justify-between px-6 h-16 border-b border-line">
        <Logo />
        <form method="post" action="/signout"><button className="text-[0.9rem] text-ink-2 hover:text-ink">Sign out</button></form>
      </header>
      <main id="main" className="flex-1 grid place-items-center px-4 py-12">
        <Panel className="w-full max-w-xl p-8 sm:p-10">
          {data.waiting.length > 0 ? (
            <>
              <h1 className="text-[1.8rem] font-extrabold">Almost there</h1>
              <p className="mt-3 text-ink-2">Their dashboard appears here as soon as they connect their Gmail.</p>
              <ul className="mt-6 space-y-3">
                {data.waiting.map((w) => (
                  <li key={w.token} className="flex items-center justify-between gap-4 rounded-xl border border-line bg-surface-2 px-4 py-3">
                    <span><strong>{w.protectedName}</strong> hasn’t connected yet.</span>
                    <Link href={`/invite/${w.token}`} className="font-semibold text-accent hover:underline underline-offset-4 whitespace-nowrap">Invite link</Link>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <>
              <MailPlus aria-hidden className="w-10 h-10 text-accent" />
              <h1 className="mt-4 text-[1.8rem] font-extrabold leading-tight">No one is protected with this account yet</h1>
              <p className="mt-3 text-ink-2">
                You’re signed in as <strong className="text-ink">{data.account.email}</strong>. ScamShield shows a dashboard to the person
                whose Gmail it checks, and to the family member who set it up.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <ButtonLink href="/signup">Protect someone</ButtonLink>
                <form method="post" action="/signout"><button className="h-11 px-5 rounded-xl text-ink-2 hover:text-ink hover:bg-surface-2 font-semibold">Use a different account</button></form>
              </div>
            </>
          )}
        </Panel>
      </main>
    </div>
  );
}
