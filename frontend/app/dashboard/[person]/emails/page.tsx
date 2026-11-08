import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { EmailsView } from "@/components/emails/EmailsView";
import { AppShell } from "@/components/shell/AppShell";
import { parsePeriod } from "@/lib/api";
import { plural } from "@/lib/format";
import { loadDashboard, viewerTimeZone } from "@/lib/load";

export const metadata: Metadata = { title: "Caught emails" };

export default async function EmailsPage({
  params, searchParams,
}: { params: Promise<{ person: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [{ person }, sp] = await Promise.all([params, searchParams]);
  const period = parsePeriod(sp.period);
  const [data, tz] = await Promise.all([loadDashboard(person, period), viewerTimeZone()]);
  const view = data.view;
  if (!view) redirect("/dashboard");
  if (view.person.id !== person) redirect(`/dashboard/${view.person.id}/emails`);
  const open = view.flagged.filter((f) => !f.markedSafe).length;
  const own = view.person.role === "self";
  return (
    <AppShell
      data={data}
      section="emails"
      period={period}
      title="Caught emails"
      subtitle={`${own ? "Your inbox" : `${view.person.name}’s inbox`}. ${view.periodLabel}: ${plural(open, "email", "emails")} to review.`}
    >
      <EmailsView view={view} tz={tz} />
    </AppShell>
  );
}
