const BASE = "/api/v1";
let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;

export function setTokens(access: string | null, refresh?: string | null) {
  accessToken = access;
  if (refresh === null) {
    sessionStorage.removeItem("refresh");
    window.dispatchEvent(new Event("session-ended"));
  }
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

async function performRefresh(): Promise<boolean> {
  const token = sessionStorage.getItem("refresh");
  if (!token) return false;
  const r = await fetch(`${BASE}/auth/token/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: token }),
  });
  // Logout or a new login may have replaced this session while the request was in flight.
  if (sessionStorage.getItem("refresh") !== token) return false;
  if (!r.ok) {
    setTokens(null, null);
    return false;
  }
  const data = await r.json();
  if (sessionStorage.getItem("refresh") !== token) return false;
  setTokens(data.access, data.refresh ?? token);
  return true;
}

async function refresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
  retry = true
): Promise<Response> {
  if (retry && !accessToken && sessionStorage.getItem("refresh")) await refresh();
  const sentToken = accessToken;
  const headers = new Headers(init.headers);
  if (sentToken) headers.set("Authorization", `Bearer ${sentToken}`);
  // Don't set Content-Type for FormData; the browser adds the boundary itself.
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && retry) {
    if ((accessToken && accessToken !== sentToken) || await refresh()) {
      return authenticatedFetch(path, init, false);
    }
    setTokens(null, null);
  }
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
