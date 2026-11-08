import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getDashboard } from "./api";
import type { Dashboard, Period } from "./types";

/** The dashboard data for this visitor, or a trip to the sign-in page. */
export async function loadDashboard(person: string | undefined, period: Period): Promise<Dashboard> {
  const data = await getDashboard(person, period);
  if (!data) redirect("/signin");
  return data;
}

export async function viewerTimeZone(): Promise<string | undefined> {
  const tz = (await cookies()).get("tz")?.value;
  try {
    if (tz) new Intl.DateTimeFormat("en-US", { timeZone: tz });
    return tz;
  } catch {
    return undefined;
  }
}
