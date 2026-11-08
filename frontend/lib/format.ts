import type { Period, Status } from "./types";

export const PERIODS: { key: Period; label: string; short: string }[] = [
  { key: "7", label: "Last 7 days", short: "7 days" },
  { key: "30", label: "Last 30 days", short: "30 days" },
  { key: "all", label: "All time", short: "All time" },
];

export function periodPhrase(period: Period): string {
  return period === "7" ? "in the last 7 days" : period === "30" ? "in the last 30 days" : "so far";
}

export function plural(n: number, one: string, many: string): string {
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
}

export function fmt(n: number): string {
  return n.toLocaleString("en-US");
}

export function ago(iso: string | null, now = Date.now()): string {
  if (!iso) return "not yet";
  const seconds = (now - new Date(iso).getTime()) / 1000;
  if (seconds < 90) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} minutes ago`;
  if (seconds < 36 * 3600) {
    const hours = Math.round(seconds / 3600);
    return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  }
  const days = Math.round(seconds / 86400);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

export function shortDate(iso: string | null, tz?: string): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: tz }).format(new Date(iso));
}

export function dateTime(iso: string | null, tz?: string): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: tz,
  }).format(new Date(iso));
}

/** "2026-10-09" -> "Oct 9" (series dates are already in the viewer's time zone). */
export function dayLabel(ymd: string, withWeekday = false): string {
  const [y, m, d] = ymd.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", timeZone: "UTC", ...(withWeekday ? { weekday: "short" } : {}),
  }).format(date);
}

export const STATUS_WORD: Record<Status, string> = {
  scam: "Scams caught",
  careful: "Take care",
  safe: "All clear",
  waiting: "Not checked yet",
};

export function delta(now: number, before: number | undefined): { text: string; dir: "up" | "down" | "flat" } | null {
  if (before === undefined) return null;
  const diff = now - before;
  if (diff === 0) return { text: "Same as before", dir: "flat" };
  return { text: `${diff > 0 ? "+" : "−"}${fmt(Math.abs(diff))} vs previous`, dir: diff > 0 ? "up" : "down" };
}

export function gmailLink(email: string, messageId?: string): string {
  const base = `https://mail.google.com/mail/u/${encodeURIComponent(email)}/`;
  return messageId ? `${base}#all/${encodeURIComponent(messageId)}` : `${base}#label/ScamShield`;
}
