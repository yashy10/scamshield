import Link from "next/link";
import { ArrowUpRight, Check, Eye, Fingerprint, LifeBuoy, ListChecks, Mail, ScanSearch, Search, Tag, Type, Users } from "lucide-react";
import { DemoDashboard } from "@/components/landing/DemoDashboard";
import { Logo } from "@/components/Logo";
import { ButtonLink, buttonClass } from "@/components/ui";
import { getSession } from "@/lib/api";

async function signedIn(): Promise<boolean> {
  try {
    return !!(await getSession()).account;
  } catch {
    return false;
  }
}

// FBI Internet Crime Complaint Center, 2025 Internet Crime Report (elder fraud section).
const PHISHING_60_PLUS = [
  { year: "2023", value: 2856 },
  { year: "2024", value: 23252 },
  { year: "2025", value: 48064 },
];

const NEWS = [
  {
    source: "FBI Internet Crime Complaint Center", date: "April 2026",
    title: "2025 Internet Crime Report",
    href: "https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf",
    note: "People 60 and over reported $7.7 billion in losses, up 59% from 2024. The average loss was $38,500.",
  },
  {
    source: "AARP", date: "April 16, 2026",
    title: "New FBI Report: $20.9 Billion Lost to Internet Crimes in 2025, Older Adults Hit Hardest",
    href: "https://www.aarp.org/money/scams-fraud/fbi-ftc-report-2025-losses.html",
    note: "Americans 60 and older reported about 60 percent more in losses than the year before.",
  },
  {
    source: "Federal Trade Commission", date: "October 19, 2026",
    title: "FTC Issues Annual Report to Congress on Agency’s Actions to Protect Older Adults",
    href: "https://www.ftc.gov/node/338049",
    note: "Fraud losses reported by older adults grew about fivefold, from about $600 million in 2020 to about $3 billion in 2025.",
  },
];

const FEATURES = [
  { icon: ScanSearch, title: "Status at a glance", body: "One ring answers “is my inbox safe?” Green, yellow or red, always with words." },
  { icon: ListChecks, title: "The evidence for every email", body: "How old the website is, what Google Safe Browsing says, and why the sender looks wrong." },
  { icon: Users, title: "One view for the whole family", body: "Look after Mom and Dad from one place, with a status dot for each." },
  { icon: Eye, title: "Warnings, not snooping", body: "Family contacts see who sent a scam and why. Never the email itself." },
  { icon: LifeBuoy, title: "Help if someone clicked", body: "A short checklist: change the password, call the bank, report it." },
  { icon: Type, title: "Made to be read", body: "Large, clear type drawn for low vision, and a bigger-text setting." },
];

export default async function Landing() {
  const authed = await signedIn();
  const top = Math.max(...PHISHING_60_PLUS.map((d) => d.value));
  return (
    <div className="overflow-x-clip">
      <header className="sticky top-0 z-30 border-b border-line/60 bg-bg/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-5 sm:px-8">
          <Logo />
          <nav aria-label="Main" className="hidden md:flex items-center gap-8 text-[0.92rem] text-ink-2">
            <a href="#how" className="hover:text-ink">How it works</a>
            <a href="#news" className="hover:text-ink">In the news</a>
            <a href="#privacy" className="hover:text-ink">Privacy</a>
          </nav>
          <div className="flex items-center gap-2">
            {authed ? (
              <ButtonLink href="/dashboard" size="sm">Open dashboard</ButtonLink>
            ) : (
              <>
                <ButtonLink href="/signin" variant="ghost" size="sm">Sign in</ButtonLink>
                <ButtonLink href="/signup" size="sm" className="hidden sm:inline-flex">Protect someone</ButtonLink>
              </>
            )}
          </div>
        </div>
      </header>

      <main id="main">
        <section className="relative">
          <div aria-hidden className="pointer-events-none absolute inset-x-0 -top-40 h-[42rem] bg-[radial-gradient(60%_50%_at_70%_30%,rgba(59,91,219,0.28),transparent_70%)]" />
          <div className="relative mx-auto grid grid-cols-1 max-w-7xl gap-14 px-5 sm:px-8 pt-14 pb-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:items-center lg:pt-20 lg:pb-28">
            <div className="rise">
              <h1 className="text-[2.6rem] sm:text-[3.6rem] lg:text-[4.1rem] font-extrabold leading-[1.02] tracking-[-0.035em]">
                A second look at every email your parents get.
              </h1>
              <p className="mt-6 max-w-xl text-[1.15rem] text-ink-2 leading-relaxed">
                ScamShield checks the links in new Gmail messages against real evidence. When an email is a scam, it’s labeled
                in Gmail and they get a plain warning, with you copied. You both see everything on one simple dashboard.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-3">
                <ButtonLink href="/signup" size="lg">Protect someone</ButtonLink>
                <a href="#how" className={buttonClass("secondary", "lg")}>How it works</a>
              </div>
              <ul className="mt-9 grid gap-2.5 text-[0.92rem] text-ink-2 sm:grid-cols-1">
                {["They sign in on Google’s own page. No passwords shared.", "Never deletes, moves or sends email.", "Family sees warnings, not emails."].map((t) => (
                  <li key={t} className="flex items-center gap-2.5"><Check aria-hidden className="w-4 h-4 text-safe-text shrink-0" strokeWidth={3} />{t}</li>
                ))}
              </ul>
            </div>
            <div className="rise" style={{ "--delay": "120ms" } as React.CSSProperties}>
              <DemoDashboard />
            </div>
          </div>
        </section>

        <section id="news" aria-labelledby="news-title" className="border-y border-line bg-raised">
          <div className="mx-auto max-w-7xl px-5 sm:px-8 py-20">
            <h2 id="news-title" className="max-w-3xl text-[2rem] sm:text-[2.6rem] font-extrabold leading-tight">
              Scam emails to older Americans have exploded.
            </h2>
            <div className="mt-12 grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
              <figure>
                <figcaption>
                  <p className="font-bold">Phishing complaints from people 60 and over</p>
                  <p className="text-[0.88rem] text-muted">Reports to the FBI each year. Phishing is now the crime older adults report most.</p>
                </figcaption>
                <div className="mt-8 grid grid-cols-3 items-end gap-6 h-64" aria-hidden>
                  {PHISHING_60_PLUS.map((d, i) => (
                    <div key={d.year} className="flex h-full flex-col items-center justify-end">
                      <span className="mb-2 font-extrabold text-[1.1rem] num">{d.value.toLocaleString("en-US")}</span>
                      <span
                        className="w-full max-w-24 rounded-t-md"
                        style={{
                          height: `calc((100% - 2rem) * ${d.value / top})`, minHeight: 4,
                          background: i === PHISHING_60_PLUS.length - 1 ? "var(--color-accent)" : "var(--color-surface-3)",
                        }}
                      />
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-3 gap-6 border-t-2 border-line-strong pt-2 text-center text-[0.85rem] text-muted" aria-hidden>
                  {PHISHING_60_PLUS.map((d) => <span key={d.year}>{d.year}</span>)}
                </div>
                <div className="sr-only">
                  <table>
                    <caption>Phishing complaints from people 60 and over, by year</caption>
                    <tbody>{PHISHING_60_PLUS.map((d) => <tr key={d.year}><th scope="row">{d.year}</th><td>{d.value}</td></tr>)}</tbody>
                  </table>
                </div>
                <p className="mt-5 text-[0.78rem] text-muted">
                  Source: <a className="underline underline-offset-2 hover:text-ink" href="https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf">FBI Internet Crime Complaint Center, 2025 Internet Crime Report</a>
                </p>
              </figure>

              <ul className="divide-y divide-line">
                {NEWS.map((n) => (
                  <li key={n.title} className="py-6 first:pt-0">
                    <p className="text-[0.8rem] text-muted"><span className="font-semibold text-ink-2">{n.source}</span><span className="ml-3">{n.date}</span></p>
                    <a href={n.href} target="_blank" rel="noreferrer" className="group mt-1.5 inline-flex items-start gap-1.5 text-[1.12rem] font-bold leading-snug hover:text-accent">
                      {n.title}
                      <ArrowUpRight aria-hidden className="w-4 h-4 mt-1 shrink-0 opacity-50 group-hover:opacity-100" />
                    </a>
                    <p className="mt-2 text-ink-2">{n.note}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section id="how" aria-labelledby="how-title" className="mx-auto max-w-7xl px-5 sm:px-8 py-24">
          <h2 id="how-title" className="text-[2rem] sm:text-[2.4rem] font-extrabold">How it works</h2>
          <ol className="mt-12 grid grid-cols-1 gap-10 md:grid-cols-3">
            {[
              { icon: Mail, title: "A new email arrives", body: "ScamShield looks at new messages in their Gmail inbox on a regular schedule. Emails without links are left alone." },
              { icon: Search, title: "Every link gets checked", body: "It looks up how long each website has existed and asks Google Safe Browsing whether the link is known to be dangerous." },
              { icon: Tag, title: "Scams get labeled and explained", body: "Risky emails get a “ScamShield” label in Gmail, and a short warning that says why, in plain words. You get a copy." },
            ].map((s, i) => (
              <li key={s.title} className="relative">
                <div className="flex items-center gap-4">
                  <span className="grid place-items-center w-11 h-11 rounded-xl border border-line-strong bg-surface font-extrabold text-accent num">{i + 1}</span>
                  <s.icon aria-hidden className="w-5 h-5 text-muted" />
                </div>
                <h3 className="mt-5 text-[1.2rem] font-bold">{s.title}</h3>
                <p className="mt-2 text-ink-2">{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="features-title" className="border-t border-line">
          <div className="mx-auto max-w-7xl px-5 sm:px-8 py-24 grid grid-cols-1 gap-14 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <div>
              <h2 id="features-title" className="text-[2rem] sm:text-[2.4rem] font-extrabold leading-tight">A dashboard the whole family can read.</h2>
              <p className="mt-4 text-[1.05rem] text-ink-2 max-w-md">Built for the person being protected and the family member looking out for them, with the same clear answers for both.</p>
              <ButtonLink href={authed ? "/dashboard" : "/signin"} variant="secondary" className="mt-8">
                {authed ? "Open your dashboard" : "Sign in to your dashboard"}
              </ButtonLink>
            </div>
            <ul className="grid grid-cols-1 gap-x-10 gap-y-9 sm:grid-cols-2">
              {FEATURES.map((f) => (
                <li key={f.title} className="flex gap-4">
                  <f.icon aria-hidden className="w-6 h-6 text-accent shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-bold text-[1.05rem]">{f.title}</h3>
                    <p className="mt-1 text-ink-2 text-[0.95rem]">{f.body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="privacy" aria-labelledby="privacy-title" className="border-t border-line bg-raised">
          <div className="mx-auto max-w-7xl px-5 sm:px-8 py-24 grid grid-cols-1 gap-12 lg:grid-cols-2">
            <div>
              <Fingerprint aria-hidden className="w-9 h-9 text-accent" />
              <h2 id="privacy-title" className="mt-5 text-[2rem] sm:text-[2.4rem] font-extrabold leading-tight">What it never does</h2>
              <ul className="mt-6 space-y-3.5 text-[1.05rem]">
                {["Delete, move or send their email.", "Show you their emails. You see warnings only.", "Ask for their password. They sign in on Google’s own page.", "Keep the text of any email."].map((t) => (
                  <li key={t} className="flex gap-3"><span aria-hidden className="mt-2.5 w-2 h-2 rounded-full bg-airmail-red shrink-0" />{t}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-[22px] border border-line-strong bg-surface p-8 sm:p-10 self-start">
              <h2 className="text-[1.6rem] font-extrabold">Set it up together</h2>
              <p className="mt-3 text-ink-2 text-[1.05rem]">You fill in a short form and send them a link. They open it and connect their own Gmail. It takes about five minutes.</p>
              <div className="mt-7 flex flex-wrap gap-3">
                <ButtonLink href="/signup" size="lg">Protect someone</ButtonLink>
                {!authed && <ButtonLink href="/signin" variant="ghost" size="lg">Sign in</ButtonLink>}
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto max-w-7xl px-5 sm:px-8 py-10 flex flex-wrap items-center justify-between gap-4 text-[0.85rem] text-muted">
          <Logo />
          <p>ScamShield labels emails and sends warnings. It never deletes, moves or sends email.</p>
        </div>
      </footer>
    </div>
  );
}
