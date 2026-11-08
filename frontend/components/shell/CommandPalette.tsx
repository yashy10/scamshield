"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { CircleHelp, Inbox, LayoutDashboard, LogOut, Search, Settings, Type } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { Period, Status } from "@/lib/types";
import { StatusDot, VerdictPill } from "@/components/ui";

interface Props {
  people: { id: string; name: string; status: Status }[];
  personId?: string;
  period: Period;
  emails: { id: string; verdict: "scam" | "suspicious" | "safe"; sender: string; domain: string | null; subject: string | null }[];
}

const SIZES = ["normal", "large", "largest"] as const;

/** ⌘K: jump to a person, a page or a caught email; change text size; sign out. */
export function CommandPalette({ people, personId, period, emails }: Props) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const q = period === "30" ? "" : `?period=${period}`;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
      if (e.key === "/" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) { e.preventDefault(); setOpen(true); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function go(href: string) { setOpen(false); router.push(href); }

  function cycleText() {
    const html = document.documentElement;
    const now = (html.dataset.text as (typeof SIZES)[number]) || "normal";
    const next = SIZES[(SIZES.indexOf(now) + 1) % SIZES.length];
    if (next === "normal") delete html.dataset.text; else html.dataset.text = next;
    try { if (next === "normal") localStorage.removeItem("ss-text"); else localStorage.setItem("ss-text", next); } catch { /* private mode */ }
  }

  async function signOut() {
    setOpen(false);
    await fetch("/signout", { method: "POST" });
    window.location.href = "/";
  }

  const item = "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[0.95rem] cursor-pointer text-ink-2 data-[selected=true]:text-ink";

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger className="inline-flex items-center gap-2 h-10 pl-3 pr-2 rounded-xl border border-line bg-surface text-muted hover:text-ink hover:border-line-strong text-[0.85rem]">
        <Search aria-hidden className="w-4 h-4" />
        <span className="hidden xl:inline">Search</span>
        <kbd className="hidden sm:inline rounded-md border border-line bg-surface-2 px-1.5 text-[0.7rem] font-sans">⌘K</kbd>
        <span className="sr-only">Search people, pages and caught emails</span>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="palette-overlay fixed inset-0 z-40 bg-black/60 backdrop-blur-[2px]" />
        <Dialog.Content
          className="fixed left-1/2 top-[12vh] z-50 w-[min(40rem,calc(100vw-2rem))] -translate-x-1/2 rounded-2xl border border-line-strong bg-surface shadow-2xl overflow-hidden focus:outline-none"
          aria-describedby={undefined}
        >
          <Dialog.Title className="sr-only">Search</Dialog.Title>
          <Command label="Search ScamShield" loop>
            <div className="flex items-center gap-3 border-b border-line px-4">
              <Search aria-hidden className="w-5 h-5 text-muted" />
              <Command.Input
                autoFocus
                placeholder="Search people, pages and caught emails"
                className="h-14 flex-1 bg-transparent text-[1rem] text-ink placeholder:text-muted focus:outline-none focus-visible:outline-none"
              />
              <kbd className="rounded-md border border-line bg-surface-2 px-1.5 text-[0.7rem] text-muted">Esc</kbd>
            </div>
            <Command.List className="max-h-[60vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-8 text-center text-muted">Nothing matches that.</Command.Empty>

              {people.length > 0 && (
                <Command.Group heading="People">
                  {people.map((p) => (
                    <Command.Item key={p.id} value={`person ${p.name}`} onSelect={() => go(`/dashboard/${p.id}${q}`)} className={item}>
                      <StatusDot status={p.status} />
                      {p.name}
                    </Command.Item>
                  ))}
                </Command.Group>
              )}

              <Command.Group heading="Pages">
                {personId && (
                  <>
                    <Command.Item value="overview dashboard home" onSelect={() => go(`/dashboard/${personId}${q}`)} className={item}>
                      <LayoutDashboard aria-hidden className="w-4 h-4 text-muted" /> Overview
                    </Command.Item>
                    <Command.Item value="caught emails scams list" onSelect={() => go(`/dashboard/${personId}/emails${q}`)} className={item}>
                      <Inbox aria-hidden className="w-4 h-4 text-muted" /> Caught emails
                    </Command.Item>
                  </>
                )}
                <Command.Item value="help if you clicked a link what to do" onSelect={() => go(`/dashboard/help${personId ? `?person=${personId}` : ""}`)} className={item}>
                  <CircleHelp aria-hidden className="w-4 h-4 text-muted" /> If you clicked a link
                </Command.Item>
                <Command.Item value="settings privacy warnings" onSelect={() => go(`/dashboard/settings${personId ? `?person=${personId}` : ""}`)} className={item}>
                  <Settings aria-hidden className="w-4 h-4 text-muted" /> Settings
                </Command.Item>
              </Command.Group>

              {emails.length > 0 && personId && (
                <Command.Group heading="Caught emails">
                  {emails.map((e) => (
                    <Command.Item
                      key={e.id}
                      value={`email ${e.sender} ${e.domain ?? ""} ${e.subject ?? ""} ${e.id}`}
                      onSelect={() => go(`/dashboard/${personId}/emails${q}${q ? "&" : "?"}email=${encodeURIComponent(e.id)}`)}
                      className={item}
                    >
                      <VerdictPill verdict={e.verdict} />
                      <span className="min-w-0 truncate"><span className="font-semibold text-ink">{e.sender}</span>{e.subject ? <span className="text-muted ml-2">{e.subject}</span> : e.domain ? <span className="text-muted ml-2">{e.domain}</span> : null}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}

              <Command.Group heading="Actions">
                <Command.Item value="text size larger bigger font" onSelect={cycleText} className={item}>
                  <Type aria-hidden className="w-4 h-4 text-muted" /> Change text size
                </Command.Item>
                <Command.Item value="sign out log out" onSelect={signOut} className={item}>
                  <LogOut aria-hidden className="w-4 h-4 text-muted" /> Sign out
                </Command.Item>
              </Command.Group>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
