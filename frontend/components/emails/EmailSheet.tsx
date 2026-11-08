"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUpRight, Check, CircleHelp, Flag, RotateCcw, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { apiPost } from "@/lib/client";
import { dateTime, gmailLink } from "@/lib/format";
import type { FlaggedEmail, InboxView } from "@/lib/types";
import { Button, VerdictPill, buttonClass, cx } from "@/components/ui";

function Step({ done, title, detail, last }: { done: boolean; title: string; detail: ReactNode; last?: boolean }) {
  return (
    <li className="relative flex gap-4 pb-5 last:pb-0">
      {!last && <span aria-hidden className="absolute left-[13px] top-7 bottom-0 w-0.5 bg-line" />}
      <span
        aria-hidden
        className={cx("relative grid place-items-center w-7 h-7 rounded-full shrink-0", done ? "bg-surface-3 text-safe-text" : "bg-surface-2 text-muted")}
      >
        {done ? <Check className="w-4 h-4" strokeWidth={3} /> : <span className="w-2 h-2 rounded-full bg-current" />}
      </span>
      <div className="min-w-0 pt-0.5">
        <p className="font-semibold">{title}</p>
        <p className="text-[0.88rem] text-muted">{detail}</p>
      </div>
    </li>
  );
}

/** One flagged email: why it was flagged, what ScamShield did about it, and what you can do now. */
export function EmailSheet({ email, view, tz, onClose }: { email: FlaggedEmail | null; view: InboxView; tz?: string; onClose: () => void }) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [marked, setMarked] = useState<FlaggedEmail["markedSafe"]>(email?.markedSafe ?? null);
  const [error, setError] = useState<string | null>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const own = view.person.role === "self";

  useEffect(() => { setMarked(email?.markedSafe ?? null); setError(null); }, [email]);

  async function toggleSafe() {
    if (!email) return;
    setSaving(true);
    setError(null);
    const res = await apiPost<{ markedSafe: FlaggedEmail["markedSafe"] }>(
      `/api/people/${encodeURIComponent(view.person.id)}/emails/${encodeURIComponent(email.id)}/safe`,
      { safe: !marked },
    );
    setSaving(false);
    if (!res.ok) { setError("That didn’t save. Try again."); return; }
    setMarked(res.data?.markedSafe ?? null);
    router.refresh();
  }

  const sender = email ? email.senderName || email.senderDomain || "Unknown sender" : "";

  return (
    <Dialog.Root open={!!email} onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay fixed inset-0 z-40 bg-black/55" />
        <Dialog.Content
          className="sheet-content fixed inset-y-0 right-0 z-50 w-full sm:w-[34rem] bg-surface border-l border-line-strong shadow-2xl flex flex-col focus:outline-none"
          aria-describedby="sheet-why"
          tabIndex={-1}
          ref={sheetRef}
          onOpenAutoFocus={(e) => { e.preventDefault(); sheetRef.current?.focus(); }}
        >
          {email && (
            <>
              <div className="flex items-start gap-4 px-6 pt-6 pb-5 border-b border-line">
                <div className="min-w-0 flex-1">
                  <VerdictPill verdict={marked ? "safe" : email.verdict} />
                  <Dialog.Title className="mt-3 text-[1.45rem] font-extrabold leading-tight break-words">{sender}</Dialog.Title>
                  {email.senderDomain && <p className="text-muted break-all">from {email.senderDomain}</p>}
                  {email.subject && <p className="mt-2 text-ink-2">“{email.subject}”</p>}
                </div>
                <Dialog.Close className="grid place-items-center w-10 h-10 -mr-2 rounded-lg text-muted hover:text-ink hover:bg-surface-2" aria-label="Close">
                  <X aria-hidden className="w-5 h-5" />
                </Dialog.Close>
              </div>

              <div className="flex-1 overflow-y-auto px-6 py-6 space-y-8">
                <section aria-labelledby="sheet-why">
                  <h3 id="sheet-why" className="text-[0.95rem] font-bold">Why ScamShield flagged it</h3>
                  {email.reasons.length ? (
                    <ul className="mt-3 space-y-2.5">
                      {email.reasons.map((r) => (
                        <li key={r} className="flex gap-3 rounded-xl bg-surface-2 border border-line px-4 py-3">
                          <Flag aria-hidden className={cx("w-4 h-4 mt-1 shrink-0", email.verdict === "scam" ? "text-scam-text" : "text-careful-text")} />
                          <span>{r}</span>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="mt-2 text-muted">No reasons were recorded for this one.</p>}
                </section>

                <section aria-labelledby="sheet-what">
                  <h3 id="sheet-what" className="text-[0.95rem] font-bold mb-4">What happened</h3>
                  <ol>
                    <Step done title="Arrived in Gmail" detail={dateTime(email.receivedAt, tz) || "Time not recorded"} />
                    <Step done title="Links checked" detail={dateTime(email.checkedAt, tz) || "Time not recorded"} />
                    <Step done={email.labeled} title={email.labeled ? "Labeled “ScamShield” in Gmail" : "Not labeled"} detail={email.labeled ? "Find it under the ScamShield label." : "The label couldn’t be added."} />
                    <Step
                      done={!!email.warnedAt}
                      title={email.warnedAt && email.warnedTo ? `Warning sent to ${email.warnedTo}` : "No warning sent"}
                      detail={email.warnedAt ? dateTime(email.warnedAt, tz) : "ScamShield only warns about scams and risky emails."}
                      last={!marked}
                    />
                    {marked && (
                      <Step done last title={`Marked safe by ${marked.by === view.person.email ? (own ? "you" : view.person.name) : own ? "your family contact" : "you"}`} detail={dateTime(marked.at, tz)} />
                    )}
                  </ol>
                </section>

                {!own && <p className="text-[0.85rem] text-muted">You see who sent it and why it was flagged, not the email itself.</p>}
              </div>

              <div className="border-t border-line px-6 py-5 space-y-3 bg-raised">
                <div className="flex flex-wrap gap-3">
                  {own && (
                    <a className={buttonClass("primary", "md")} href={gmailLink(view.person.email, email.id)} target="_blank" rel="noreferrer">
                      Open in Gmail <ArrowUpRight aria-hidden className="w-4 h-4" />
                    </a>
                  )}
                  <Button variant="secondary" onClick={toggleSafe} disabled={saving}>
                    {marked ? <><RotateCcw aria-hidden className="w-4 h-4" /> Undo “safe”</> : <><ShieldCheck aria-hidden className="w-4 h-4" /> It’s not a scam</>}
                  </Button>
                  <a className={buttonClass("ghost", "md")} href="https://reportfraud.ftc.gov/" target="_blank" rel="noreferrer">
                    Report to the FTC <ArrowUpRight aria-hidden className="w-4 h-4" />
                  </a>
                </div>
                {error && <p role="alert" className="text-scam-text text-[0.9rem]">{error}</p>}
                <Link href={`/dashboard/help?person=${view.person.id}`} className="inline-flex items-center gap-2 text-[0.9rem] font-semibold text-accent hover:underline underline-offset-4">
                  <CircleHelp aria-hidden className="w-4 h-4" /> Clicked a link in this email? Here’s what to do
                </Link>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
