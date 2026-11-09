import { ApiError } from "./client";

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 429) return "Too many attempts. Wait a minute and try again.";
    const b = e.body?.error ?? e.body;
    if (b && typeof b === "object") {
      if (typeof b.message === "string") return b.message;
      const details = Array.isArray(b.details)
        ? b.details.flatMap((item: any) => item.messages ?? item.message ?? []).filter(Boolean)
        : [];
      if (details.length) return details.join(" ");
      const parts = Object.values(b).flat().map((value) => typeof value === "string" ? value : JSON.stringify(value));
      if (parts.length) return parts.join(" ");
    }
    return e.message;
  }
  if (e instanceof Error) return e.message;
  return "Cannot reach the server. Is the backend running?";
}
