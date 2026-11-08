import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { ActivityChart } from "@/components/ActivityChart";
import { AttentionList } from "@/components/dashboard/AttentionList";
import { KpiPanel } from "@/components/dashboard/KpiPanel";
import { QuickHelp } from "@/components/dashboard/QuickHelp";
import { StatusPanel } from "@/components/dashboard/StatusPanel";
import { AppShell } from "@/components/shell/AppShell";
import { Panel, PanelHeader } from "@/components/ui";
import { parsePeriod } from "@/lib/api";
import { loadDashboard, viewerTimeZone } from "@/lib/load";

export const metadata: Metadata = { title: "Overview" };

export default async function OverviewPage({
  params, searchParams,
}: { params: Promise<{ person: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [{ person }, sp] = await Promise.all([params, searchParams]);
  const period = parsePeriod(sp.period);
  const [data, tz] = await Promise.all([loadDashboard(person, period), viewerTimeZone()]);
  const view = data.view;
  if (!view) redirect("/dashboard");
  if (view.person.id !== person) redirect(`/dashboard/${view.person.id}`);

  const own = view.person.role === "self";
  return (
    <AppShell
      data={data}
      section="overview"
      period={period}
      title={own ? "Your inbox" : `${view.person.name}’s inbox`}
      subtitle={own ? view.person.email : `${view.person.email}. You’re ${view.person.name}’s family contact.`}
    >
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="xl:col-span-12 rise"><StatusPanel view={view} /></div>
        <div className="xl:col-span-12 rise" style={{ "--delay": "80ms" } as React.CSSProperties}><KpiPanel view={view} /></div>

        <Panel className="xl:col-span-12 rise" style={{ "--delay": "140ms" } as React.CSSProperties} aria-labelledby="activity-title">
          <PanelHeader
            id="activity-title"
            title={view.series.unit === "day" ? "Emails checked each day" : "Emails checked each week"}
            aside={<span className="text-[0.82rem] text-muted">{view.periodLabel}</span>}
          />
          <ActivityChart points={view.series.points} unit={view.series.unit} />
        </Panel>

        <div className="xl:col-span-7 rise" style={{ "--delay": "200ms" } as React.CSSProperties}><AttentionList view={view} tz={tz} /></div>
        <div className="xl:col-span-5 rise" style={{ "--delay": "240ms" } as React.CSSProperties}><QuickHelp view={view} /></div>
      </div>
    </AppShell>
  );
}
