"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Keeps the dashboard current: every minute while the tab is visible, every 5 seconds during a scan. */
export function AutoRefresh({ fast = false }: { fast?: boolean }) {
  const router = useRouter();
  useEffect(() => {
    const every = fast ? 5_000 : 60_000;
    const tick = () => { if (document.visibilityState === "visible") router.refresh(); };
    const id = window.setInterval(tick, every);
    document.addEventListener("visibilitychange", tick);
    return () => { window.clearInterval(id); document.removeEventListener("visibilitychange", tick); };
  }, [fast, router]);
  return null;
}
