/** Browser-side calls to the Python API (same origin). The header marks them as coming from this app. */
export async function apiPost<T>(path: string, body?: unknown): Promise<{ ok: boolean; status: number; data: T | null }> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-ScamShield-Client": "web" },
    body: body === undefined ? "{}" : JSON.stringify(body),
  });
  let data: T | null = null;
  try { data = (await res.json()) as T; } catch { /* empty body */ }
  return { ok: res.ok, status: res.status, data };
}

export async function apiGet<T>(path: string): Promise<T | null> {
  const res = await fetch(path, { headers: { accept: "application/json" }, cache: "no-store" });
  return res.ok ? ((await res.json()) as T) : null;
}
