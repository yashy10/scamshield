import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { Check, CircleAlert, Clock3, X } from "lucide-react";
import type { Status } from "@/lib/types";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

const BUTTON = {
  primary: "bg-primary text-white hover:bg-primary-hover",
  secondary: "bg-surface-2 text-ink border border-line-strong hover:bg-surface-3",
  ghost: "text-ink-2 hover:text-ink hover:bg-surface-2",
  danger: "bg-scam text-white hover:brightness-110",
} as const;

const SIZE = {
  sm: "h-9 px-3.5 text-[0.85rem] gap-1.5 rounded-lg",
  md: "h-11 px-5 text-[0.95rem] gap-2 rounded-xl",
  lg: "h-14 px-7 text-[1.05rem] gap-2.5 rounded-xl",
} as const;

type Variant = keyof typeof BUTTON;
type Size = keyof typeof SIZE;

export function buttonClass(variant: Variant = "primary", size: Size = "md", extra?: string): string {
  return cx(
    "inline-flex items-center justify-center font-semibold whitespace-nowrap transition-colors duration-150",
    "disabled:opacity-60 disabled:cursor-not-allowed select-none",
    BUTTON[variant],
    SIZE[size],
    extra,
  );
}

export function Button({ variant, size, className, ...props }: ComponentProps<"button"> & { variant?: Variant; size?: Size }) {
  return <button className={buttonClass(variant, size, className)} {...props} />;
}

export function ButtonLink({ variant, size, className, ...props }: ComponentProps<typeof Link> & { variant?: Variant; size?: Size }) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}

export const STATUS_COLOR: Record<Status, string> = {
  scam: "var(--color-scam)",
  careful: "var(--color-careful)",
  safe: "var(--color-safe)",
  waiting: "var(--color-waiting)",
};

/** A status is never color alone: this icon rides with every status color. */
export function StatusIcon({ status, className }: { status: Status; className?: string }) {
  const Icon = status === "scam" ? X : status === "careful" ? CircleAlert : status === "safe" ? Check : Clock3;
  return <Icon aria-hidden className={className} strokeWidth={3} />;
}

export function StatusBadge({ status, size = 56 }: { status: Status; size?: number }) {
  const fg = status === "scam" ? "#fff" : status === "waiting" ? "var(--color-ink)" : "var(--color-bg)";
  return (
    <span
      className="inline-grid place-items-center rounded-full shrink-0"
      style={{ width: size, height: size, background: STATUS_COLOR[status], color: fg }}
    >
      <StatusIcon status={status} className="w-[55%] h-[55%]" />
    </span>
  );
}

const PILL: Record<"scam" | "suspicious" | "safe", { label: string; cls: string; status: Status }> = {
  scam: { label: "Scam", cls: "bg-scam text-white", status: "scam" },
  suspicious: { label: "Be careful", cls: "bg-careful text-bg", status: "careful" },
  safe: { label: "Marked safe", cls: "bg-surface-3 text-ink-2", status: "safe" },
};

export function VerdictPill({ verdict }: { verdict: "scam" | "suspicious" | "safe" }) {
  const p = PILL[verdict];
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full pl-1.5 pr-2.5 py-0.5 text-[0.75rem] font-bold whitespace-nowrap", p.cls)}>
      <StatusIcon status={p.status} className="w-3.5 h-3.5" />
      {p.label}
    </span>
  );
}

export function StatusDot({ status, pulse }: { status: Status; pulse?: boolean }) {
  return (
    <span
      aria-hidden
      className={cx("inline-block w-2.5 h-2.5 rounded-full shrink-0", pulse && status === "scam" && "pulse-dot")}
      style={{ background: STATUS_COLOR[status], boxShadow: `0 0 0 3px color-mix(in oklab, ${STATUS_COLOR[status]} 22%, transparent)` }}
    />
  );
}

export function Panel({ className, children, ...props }: ComponentProps<"section">) {
  return (
    <section className={cx("rounded-[var(--radius-card)] border border-line bg-surface", className)} {...props}>
      {children}
    </section>
  );
}

export function PanelHeader({ title, aside, id }: { title: ReactNode; aside?: ReactNode; id?: string }) {
  return (
    <div className="flex items-center justify-between gap-4 px-6 pt-5 pb-3">
      <h2 id={id} className="text-[1.05rem] font-bold">{title}</h2>
      {aside}
    </div>
  );
}

export function Swatch({ color }: { color: string }) {
  return <span aria-hidden className="inline-block w-3 h-3 rounded-[3px] shrink-0" style={{ background: color }} />;
}
