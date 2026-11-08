import type { Metadata } from "next";
import Link from "next/link";
import { Frame } from "@/components/onboarding/Frame";
import { SignupForm } from "@/components/onboarding/SignupForm";

export const metadata: Metadata = { title: "Protect someone" };

export default function SignupPage() {
  return (
    <Frame aside={<Link href="/signin" className="text-[0.9rem] font-semibold text-ink-2 hover:text-ink">Sign in</Link>}>
      <h1 className="text-[2rem] font-extrabold leading-tight">Set up ScamShield for someone</h1>
      <p className="mt-3 text-ink-2 text-[1.05rem]">You’ll get a link to send them. They open it and connect their own Gmail. It takes about five minutes.</p>
      <SignupForm />
    </Frame>
  );
}
