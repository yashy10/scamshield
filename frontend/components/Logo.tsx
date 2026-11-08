import Link from "next/link";

/** The envelope mark with its airmail edge: one of the two places the stripe appears. */
export function Logo({ href = "/", compact = false }: { href?: string; compact?: boolean }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2.5 font-extrabold text-[1.05rem] tracking-tight text-ink rounded-md">
      <svg viewBox="0 0 36 26" className="w-8 h-6 shrink-0" aria-hidden>
        <defs>
          <pattern id="ss-airmail" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="4" height="8" fill="#e5484d" />
            <rect x="4" width="4" height="8" fill="#5b7cff" />
          </pattern>
        </defs>
        <rect x="0.5" y="0.5" width="35" height="25" rx="5" fill="url(#ss-airmail)" />
        <rect x="3" y="3" width="30" height="20" rx="3" fill="#18223b" />
        <path d="M5.5 6.5 18 15.5 30.5 6.5" fill="none" stroke="#eef2fa" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {!compact && <span>ScamShield</span>}
    </Link>
  );
}
