import { api, authenticatedFetch, json } from "./client";

export type EvaluationStatus = {
  id: string;
  status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "TIMED_OUT";
  task_type?: string;
  dataset_sha256?: string;
  target_column?: string;
  model_sha256?: string;
  error_code?: string;
  error_message?: string;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
};
export type EvaluationDetail = EvaluationStatus & {
  metrics_json?: Record<string, unknown>;
  charts_json?: Record<string, any>;
};
export type EvaluationList = { count: number; next: string | null; previous: string | null; results: EvaluationStatus[] };

export function createEvaluation(model_id: string, dataset_id: string, task_type?: string, workspace_id?: string) {
  return api<EvaluationStatus>("/evaluations", json("POST", {
    model_id, dataset_id, ...(task_type ? { task_type } : {}),
    ...(workspace_id ? { workspace_id } : {}),
  }));
}
export const getEvaluationStatus = (id: string) => api<EvaluationStatus>(`/evaluations/${id}/status`);
export const getEvaluation = (id: string) => api<EvaluationDetail>(`/evaluations/${id}`);
export const getHistory = (page = 1, filters: Record<string, string> = {}) => {
  const params = new URLSearchParams({ page: String(page) });
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  return api<EvaluationList>(`/evaluations?${params}`);
};
export const deleteEvaluation = (id: string) => api(`/evaluations/${id}`, { method: "DELETE" });
export const createComparison = (evaluation_ids: string[]) =>
  api<any>("/comparisons", json("POST", { evaluation_ids }));

export async function downloadReport(path: string, filename: string) {
  const response = await authenticatedFetch(path);
  if (!response.ok) throw new Error(`Download failed (${response.status}).`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
