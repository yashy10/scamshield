import type { ReactNode } from "react";
import { Logo } from "@/components/Logo";
import { cx } from "@/components/ui";

/** The quiet frame for sign-in and onboarding: logo, one centered panel with the airmail edge. */
export function Frame({ children, wide = false, aside }: { children: ReactNode; wide?: boolean; aside?: ReactNode }) {
  return (
    <div className="min-h-dvh flex flex-col">
      <header className="mx-auto w-full max-w-7xl flex items-center justify-between px-5 sm:px-8 h-16">
        <Logo />
        {aside}
      </header>
      <main id="main" className="flex-1 grid place-items-start sm:place-items-center px-4 py-8 sm:py-14">
        <div className={cx("relative w-full mx-auto rounded-[22px] border border-line-strong bg-surface overflow-hidden", wide ? "max-w-3xl" : "max-w-xl")}>
          <div aria-hidden className="airmail h-1.5" />
          <div className="p-7 sm:p-10">{children}</div>
        </div>
      </main>
    </div>
  );
}
