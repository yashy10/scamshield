import Link from "next/link";
import type { ReactNode } from "react";
import { CircleHelp, Inbox, LayoutDashboard, LogOut, Settings } from "lucide-react";
import { Logo } from "@/components/Logo";
import { cx, StatusDot } from "@/components/ui";
import { PERIODS, plural } from "@/lib/format";
import type { Dashboard, Period, PersonSummary } from "@/lib/types";
import { AutoRefresh } from "./AutoRefresh";
import { CommandPalette } from "./CommandPalette";
import { MobileNav } from "./MobileNav";
import { ScanButton } from "./ScanButton";

export type Section = "overview" | "emails" | "help" | "settings";

function personStatusText(p: PersonSummary): string {
  if (p.status === "waiting") return "Not checked yet";
  if (p.status === "scam") return plural(p.flagged30d, "flagged email", "flagged emails");
  if (p.status === "careful") return "Needs a careful look";
  return "All clear";
}

export function hrefFor(section: Section, personId: string | undefined, period: Period): string {
  if (section === "help" || section === "settings") return `/dashboard/${section}${personId ? `?person=${personId}` : ""}`;
  if (!personId) return "/dashboard";
  const q = period === "30" ? "" : `?period=${period}`;
  return `/dashboard/${personId}${section === "emails" ? "/emails" : ""}${q}`;
}

const URGENCY = { scam: 0, careful: 1, safe: 2, waiting: 3 } as const;

/** You first, then whoever needs attention most. */
function byUrgency(a: PersonSummary, b: PersonSummary): number {
  if (a.role !== b.role) return a.role === "self" ? -1 : 1;
  return URGENCY[a.status] - URGENCY[b.status] || a.name.localeCompare(b.name);
}

function SidebarContent({ data, section, personId, period }: { data: Dashboard; section: Section; personId?: string; period: Period }) {
  const flaggedCount = data.view?.flagged.filter((f) => !f.markedSafe).length ?? 0;
  const nav = [
    { key: "overview" as const, label: "Overview", icon: LayoutDashboard },
    { key: "emails" as const, label: "Caught emails", icon: Inbox, count: flaggedCount },
    { key: "help" as const, label: "If you clicked a link", icon: CircleHelp },
    { key: "settings" as const, label: "Settings", icon: Settings },
  ];
  const guardianOf = data.people.filter((p) => p.role === "guardian");
  const self = data.people.find((p) => p.role === "self");
  return (
    <div className="flex flex-col h-full">
      <div className="px-5 pt-5 pb-6"><Logo href="/" /></div>

      <nav aria-label="Dashboard" className="px-3">
        <ul className="space-y-1">
          {nav.map((item) => {
            const current = item.key === section;
            const Icon = item.icon;
            return (
              <li key={item.key}>
                <Link
                  href={hrefFor(item.key, personId, period)}
                  aria-current={current ? "page" : undefined}
                  className={cx(
                    "flex items-center gap-3 rounded-xl px-3 h-11 text-[0.95rem] font-semibold transition-colors",
                    current ? "bg-surface-2 text-ink" : "text-ink-2 hover:text-ink hover:bg-surface",
                  )}
                >
                  <Icon aria-hidden className={cx("w-[18px] h-[18px]", current ? "text-accent" : "text-muted")} />
                  <span className="flex-1">{item.label}</span>
                  {item.count ? (
                    <span className="num rounded-full bg-scam/20 text-scam-text text-[0.75rem] font-bold px-2 py-0.5">{item.count}</span>
                  ) : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {data.people.length > 0 && (
        <div className="mt-8 px-3">
          <h2 className="px-3 mb-2 text-[0.8rem] text-muted font-semibold">
            {guardianOf.length ? (self ? "Inboxes you can see" : "People you look after") : "Your inbox"}
          </h2>
          <ul className="space-y-1">
            {[...data.people].sort(byUrgency).map((p) => {
              const current = p.id === personId;
              return (
                <li key={p.id}>
                  <Link
                    href={hrefFor(section === "emails" ? "emails" : "overview", p.id, period)}
                    aria-current={current ? "true" : undefined}
                    className={cx(
                      "flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors",
                      current ? "bg-surface-2" : "hover:bg-surface",
                    )}
                  >
                    <StatusDot status={p.status} pulse />
                    <span className="min-w-0 flex-1">
                      <span className="block font-semibold text-[0.95rem] truncate">{p.role === "self" ? "You" : p.name}</span>
                      <span className="block text-[0.78rem] text-muted truncate">{personStatusText(p)}</span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {data.waiting.length > 0 && (
        <div className="mt-6 px-6 text-[0.82rem] text-muted space-y-1.5">
          {data.waiting.map((w) => (
            <p key={w.token}>
              {w.protectedName} hasn’t connected yet.{" "}
              <Link className="text-accent underline underline-offset-2" href={`/invite/${w.token}`}>Invite link</Link>
            </p>
          ))}
        </div>
      )}

      <div className="mt-auto p-3">
        <div className="flex items-center gap-3 rounded-xl px-3 py-3 border border-line">
          <span className="grid place-items-center w-9 h-9 rounded-full bg-surface-3 text-[0.9rem] font-bold shrink-0" aria-hidden>
            {(data.account.name || data.account.email).slice(0, 1).toUpperCase()}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[0.85rem] font-semibold truncate">{data.account.name || "Signed in"}</span>
            <span className="block text-[0.75rem] text-muted truncate">{data.account.email}</span>
          </span>
          <form method="post" action="/signout">
            <button type="submit" className="grid place-items-center w-9 h-9 rounded-lg text-muted hover:text-ink hover:bg-surface-2" aria-label="Sign out">
              <LogOut aria-hidden className="w-[18px] h-[18px]" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export function AppShell({
  data, section, period, title, subtitle, children, showPeriod = true,
}: {
  data: Dashboard; section: Section; period: Period; title: ReactNode; subtitle?: ReactNode; children: ReactNode; showPeriod?: boolean;
}) {
  const view = data.view;
  const personId = view?.person.id;
  const scanning = view?.scan.status === "running" || view?.scan.status === "started";
  const sidebar = <SidebarContent data={data} section={section} personId={personId} period={period} />;
  const paletteEmails = (view?.flagged ?? []).map((f) => ({
    id: f.id, verdict: f.markedSafe ? ("safe" as const) : f.verdict, sender: f.senderName || f.senderDomain || "Unknown sender",
    domain: f.senderDomain, subject: f.subject,
  }));

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[17rem_1fr]">
      <aside className="hidden lg:block sticky top-0 h-dvh border-r border-line bg-raised overflow-y-auto">{sidebar}</aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur supports-[backdrop-filter]:bg-bg/70">
          <div className="flex items-center gap-3 px-4 sm:px-6 lg:px-8 h-16 max-w-[84rem] mx-auto">
            <MobileNav>{sidebar}</MobileNav>
            <div className="min-w-0 flex-1">
              <h1 className="text-[1.15rem] sm:text-[1.3rem] font-extrabold truncate">{title}</h1>
              {subtitle && <p className="hidden sm:block text-[0.8rem] text-muted truncate -mt-0.5">{subtitle}</p>}
            </div>
            {showPeriod && view && (
              <nav aria-label="Time period" className="hidden md:flex rounded-xl border border-line bg-surface p-1">
                {PERIODS.map((p) => (
                  <Link
                    key={p.key}
                    href={section === "emails" ? hrefFor("emails", personId, p.key) : hrefFor("overview", personId, p.key)}
                    aria-current={p.key === period ? "page" : undefined}
                    className={cx(
                      "px-3 h-8 inline-flex items-center rounded-lg text-[0.82rem] font-semibold transition-colors",
                      p.key === period ? "bg-surface-3 text-ink" : "text-ink-2 hover:text-ink",
                    )}
                  >
                    {p.short}
                  </Link>
                ))}
              </nav>
            )}
            {view && <ScanButton personId={view.person.id} initial={view.scan} />}
            <CommandPalette
              people={data.people.map((p) => ({ id: p.id, name: p.role === "self" ? "You" : p.name, status: p.status }))}
              personId={personId}
              period={period}
              emails={paletteEmails}
            />
          </div>
          {showPeriod && view && (
            <nav aria-label="Time period" className="md:hidden flex gap-1 px-4 pb-3">
              {PERIODS.map((p) => (
                <Link
                  key={p.key}
                  href={section === "emails" ? hrefFor("emails", personId, p.key) : hrefFor("overview", personId, p.key)}
                  aria-current={p.key === period ? "page" : undefined}
                  className={cx(
                    "flex-1 h-9 inline-flex items-center justify-center rounded-lg text-[0.82rem] font-semibold border",
                    p.key === period ? "bg-surface-3 text-ink border-line-strong" : "text-ink-2 border-line",
                  )}
                >
                  {p.short}
                </Link>
              ))}
            </nav>
          )}
        </header>

        <main id="main" className="px-4 sm:px-6 lg:px-8 py-6 lg:py-8 max-w-[84rem] mx-auto">{children}</main>
      </div>
      <AutoRefresh fast={scanning} />
    </div>
  );
}
