const BASE = "/api/v1";
let accessToken: string | null = null;

export function setTokens(access: string | null, refresh?: string | null) {
  accessToken = access;
  if (refresh === null) sessionStorage.removeItem("refresh");
  else if (refresh) sessionStorage.setItem("refresh", refresh);
}

export const isLoggedIn = () =>
  !!accessToken || !!sessionStorage.getItem("refresh");

export function currentRole(): string | null {
  const token = accessToken || sessionStorage.getItem("refresh");
  if (!token) return null;
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(payload)).role ?? null;
  } catch {
    return null;
  }
}

export class ApiError extends Error {
  public status: number;
  public body: any;
  constructor(status: number, body: any) {
    super(body?.detail ?? `Request failed (${status})`);
    this.status = status;
    this.body = body;
  }
}

async function refresh(): Promise<boolean> {
  const token = sessionStorage.getItem("refresh");
  if (!token) return false;
  const r = await fetch(`${BASE}/auth/token/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: token }),
  });
  if (!r.ok) {
    setTokens(null, null);
    return false;
  }
  const data = await r.json();
  setTokens(data.access, data.refresh ?? token); // refresh tokens rotate
  return true;
}

export async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
  retry = true
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  // Don't set Content-Type for FormData; the browser adds the boundary itself.
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && retry && (await refresh()))
    return authenticatedFetch(path, init, false);
  return res;
}

export async function api<T = any>(
  path: string,
  init: RequestInit = {},
  retry = true
): Promise<T> {
  const res = await authenticatedFetch(path, init, retry);

  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

export const json = (method: string, data: unknown): RequestInit => ({
  method,
  body: JSON.stringify(data),
});
