import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Frame } from "@/components/onboarding/Frame";
import { DevSignIn } from "@/components/onboarding/DevSignIn";
import { getSession } from "@/lib/api";

export const metadata: Metadata = { title: "Sign in" };

const MESSAGES: Record<string, string> = {
  cancelled: "Sign-in was cancelled. You can try again.",
  restart: "This sign-in didn’t start in this browser, or it expired. Try again.",
  google: "Google didn’t confirm the sign-in. Try again in a minute.",
  wrong_client: "That sign-in wasn’t meant for ScamShield.",
  expired: "That sign-in expired. Try again.",
  unverified: "Google hasn’t verified the email address on that account.",
  not_configured: "Google sign-in isn’t set up on this site yet.",
  bad_email: "Enter an email address like name@example.com.",
};

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="w-5 h-5" aria-hidden>
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

export default async function SignIn({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [session, sp] = await Promise.all([getSession(), searchParams]);
  if (session.account) redirect("/dashboard");
  const error = typeof sp.error === "string" ? MESSAGES[sp.error] ?? "Something went wrong. Try again." : null;
  return (
    <Frame aside={<Link href="/signup" className="text-[0.9rem] font-semibold text-ink-2 hover:text-ink">Protect someone</Link>}>
      <h1 className="text-[2rem] font-extrabold leading-tight">Sign in to ScamShield</h1>
      <p className="mt-3 text-ink-2 text-[1.05rem]">
        Use the Google account whose Gmail ScamShield checks, or the email address you gave when you set it up for someone.
      </p>
      {error && <p role="alert" className="mt-5 rounded-xl border border-scam/50 bg-scam/10 px-4 py-3 text-scam-text">{error}</p>}

      {session.googleSignIn ? (
        <form method="post" action="/signin/google" className="mt-7">
          <button type="submit" className="w-full inline-flex items-center justify-center gap-3 h-14 rounded-xl bg-white text-[#1f1f1f] text-[1.02rem] font-semibold hover:bg-[#f2f4f8] transition-colors">
            <GoogleMark /> Sign in with Google
          </button>
          <p className="mt-3 text-center text-[0.82rem] text-muted">Google only tells ScamShield your name and email address.</p>
        </form>
      ) : (
        <p className="mt-7 rounded-xl border border-line bg-surface-2 px-4 py-3 text-ink-2">Google sign-in isn’t set up on this site yet.</p>
      )}

      {session.devSignIn && <DevSignIn />}

      <p className="mt-8 text-[0.92rem] text-muted">New to ScamShield? <Link href="/signup" className="font-semibold text-accent hover:underline underline-offset-4">Set it up for someone</Link></p>
    </Frame>
  );
}
