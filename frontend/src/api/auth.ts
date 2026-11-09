import { api, json, setTokens } from "./client";

export async function login(email: string, password: string) {
  const d = await api("/auth/login", json("POST", { email, password }), false);
  setTokens(d.access, d.refresh);
}

export const register = (email: string, password: string) =>
  api("/auth/register", json("POST", { email, password }), false);

export async function logout() {
  const refresh = sessionStorage.getItem("refresh");
  try {
    await api("/auth/logout", json("POST", { refresh }));
  } finally {
    setTokens(null, null);
  }
}