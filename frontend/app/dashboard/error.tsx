"use client";

import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui";

export default function DashboardError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="min-h-dvh grid place-items-center px-4">
      <div className="max-w-md text-center">
        <Logo />
        <h1 className="mt-8 text-[1.6rem] font-extrabold">ScamShield can’t load your dashboard right now</h1>
        <p className="mt-3 text-ink-2">The page couldn’t reach ScamShield’s server. Try again in a moment.</p>
        <Button className="mt-6" onClick={reset}>Try again</Button>
      </div>
    </div>
  );
}
