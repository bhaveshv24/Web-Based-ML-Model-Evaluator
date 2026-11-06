import { api, json } from "./client";

export type ModelArtifact = { id: string; original_filename: string; size_bytes: number; sha256: string };
export type Dataset = {
  id: string;
  original_filename: string;
  columns: string[];
  row_count: number;
  suggested_target: string | null;
  target_column: string | null;
};
export type CompatibilityCheck = {
  code: string;
  message: string;
  expected: unknown;
  actual: unknown;
};
export type CompatibilityReport = {
  id: string;
  model_id: string;
  dataset_id: string;
  result: "PASSED" | "FAILED";
  checks: CompatibilityCheck[];
};

export function uploadModel(file: File) {
  const form = new FormData();
  form.append("file", file);
  return api<ModelArtifact>("/models", { method: "POST", body: form });
}

export function uploadDataset(file: File) {
  const form = new FormData();
  form.append("file", file);
  return api<Dataset>("/datasets", { method: "POST", body: form });
}

export function updateTarget(id: string, target_column: string) {
  return api<Dataset>(`/datasets/${id}`, json("PATCH", { target_column }));
}

export function checkCompatibility(model_id: string, dataset_id: string) {
  return api<CompatibilityReport>("/compatibility-reports", json("POST", { model_id, dataset_id }));
}
