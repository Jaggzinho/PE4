import { apiFetch } from "./client";

export type ImportResult = {
  materials: number; properties: number; tests: number; measurements: number; sinottico_items: number;
  component_types: number; components: number; material_component_defaults: number;
};
export type ImportXlsmResult = { logs: string[]; result: ImportResult };
export type ImportJob = {
  job_id: string; kind: string; status: "queued" | "running" | "succeeded" | "failed";
  progress: number; messages: string[]; result: ImportResult | null; error: string | null;
  created_at: string; updated_at: string;
};
export type ImportJobCreated = { job_id: string; status: "queued" | "running" };

function upload(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}

export function importXlsm(file: File): Promise<ImportXlsmResult> { return apiFetch("/api/import/xlsm", { method: "POST", body: upload(file) }); }
export function submitImport(file: File): Promise<ImportJobCreated> { return apiFetch("/api/imports", { method: "POST", body: upload(file) }); }
export function importJob(jobId: string): Promise<ImportJob> { return apiFetch(`/api/jobs/${encodeURIComponent(jobId)}`); }
export function recentImportJobs(): Promise<ImportJob[]> { return apiFetch("/api/jobs?limit=20"); }
