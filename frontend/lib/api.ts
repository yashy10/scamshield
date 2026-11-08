import "server-only";
import { cookies, headers } from "next/headers";
import type { Dashboard, InviteInfo, Period, SessionInfo } from "./types";

// On Vercel, SCAMSHIELD_API_URL is the service binding to the Python service (see vercel.json).
const API = (process.env.SCAMSHIELD_API_URL ?? "http://127.0.0.1:8080").replace(/\/$/, "");

export class BackendDown extends Error {}

/**
 * Calls the Python API from the server with the visitor's Cookie header passed through untouched.
 * (Not the parsed cookie jar: it keeps one cookie per name, so a same-named cookie from another app on
 * localhost could replace ours.)
 */
async function get<T>(path: string): Promise<{ status: number; data: T | null }> {
  const incoming = await headers();
  const forward: Record<string, string> = { cookie: incoming.get("cookie") ?? "", accept: "application/json" };
  // The Python service reaches AWS with Vercel's OIDC token, which arrives on each request. Calls over the
  // service binding are internal, so pass this request's token along.
  const oidc = incoming.get("x-vercel-oidc-token");
  if (oidc) forward["x-vercel-oidc-token"] = oidc;
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      headers: forward,
      cache: "no-store",
    });
  } catch (err) {
    throw new BackendDown(`ScamShield's server didn't answer (${(err as Error).message}).`);
  }
  if (res.status >= 500) throw new BackendDown(`ScamShield's server had a problem (${res.status}).`);
  const data = res.ok ? ((await res.json()) as T) : null;
  return { status: res.status, data };
}

export async function getSession(): Promise<SessionInfo> {
  const { data } = await get<SessionInfo>("/api/session");
  return data ?? { account: null, googleSignIn: false, devSignIn: false };
}

export async function getDashboard(person: string | undefined, period: Period): Promise<Dashboard | null> {
  const jar = await cookies();
  const params = new URLSearchParams({ period });
  if (person) params.set("person", person);
  const tz = jar.get("tz")?.value;
  if (tz) params.set("tz", tz);
  const { status, data } = await get<Dashboard>(`/api/dashboard?${params}`);
  if (status === 401) return null;
  return data;
}

export async function getInvite(token: string): Promise<InviteInfo | null> {
  if (!/^[A-Za-z0-9_-]{8,64}$/.test(token)) return null;
  const { data } = await get<InviteInfo>(`/api/invites/${encodeURIComponent(token)}`);
  return data;
}

export function parsePeriod(value: string | string[] | undefined): Period {
  return value === "7" || value === "all" ? value : "30";
}
