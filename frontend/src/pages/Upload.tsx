import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { logout } from "../api/auth";
import { errorMessage } from "../api/errors";
import { api, currentRole } from "../api/client";
import { checkCompatibility, type CompatibilityReport, type Dataset, type ModelArtifact, updateTarget, uploadDataset, uploadModel } from "../api/ingestion";
import { createEvaluation } from "../api/evaluations";

const MODEL_LIMIT = 100 * 1024 * 1024;
const DATASET_LIMIT = 50 * 1024 * 1024;

export default function Upload() {
  const navigate = useNavigate();
  const [model, setModel] = useState<ModelArtifact | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [target, setTarget] = useState("");
  const [taskType, setTaskType] = useState("");
  const [report, setReport] = useState<CompatibilityReport | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [workspaces, setWorkspaces] = useState<Array<{ id: string; name: string }>>([]);
  const [workspace, setWorkspace] = useState("");
  useEffect(() => {
    let active = true;
    api<Array<{ id: string; name: string }>>("/workspaces/available")
      .then((data) => { if (active) setWorkspaces(data); })
      .catch((cause) => { if (active) setError(errorMessage(cause)); });
    return () => { active = false; };
  }, []);

  async function action(label: string, callback: () => Promise<void>) {
    setBusy(label); setError(""); setNotice("");
    try { await callback(); }
    catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(""); }
  }

  function chooseModel(file?: File) {
    if (!file) return;
    setModel(null); setReport(null);
    void action("model", async () => {
      if (!/\.(pkl|joblib|onnx)$/i.test(file.name)) throw new Error("Model must be .pkl, .joblib or .onnx.");
      if (file.size > MODEL_LIMIT) throw new Error("Model must be 100 MB or smaller.");
      setModel(await uploadModel(file)); setReport(null);
    });
  }

  function chooseDataset(file?: File) {
    if (!file) return;
    setDataset(null); setTarget(""); setReport(null);
    void action("dataset", async () => {
      if (!file.name.toLowerCase().endsWith(".csv")) throw new Error("Dataset must be a .csv file.");
      if (file.size > DATASET_LIMIT) throw new Error("Dataset must be 50 MB or smaller.");
      const uploaded = await uploadDataset(file);
      setDataset(uploaded); setTarget(uploaded.target_column ?? uploaded.suggested_target ?? ""); setReport(null);
    });
  }

  function changeTarget(value: string) {
    setTarget(value); setReport(null);
    if (!dataset) return;
    void action("target", async () => {
      const updated = await updateTarget(dataset.id, value);
      setDataset(updated); setTarget(updated.target_column ?? value);
    });
  }

  function runCompatibility() {
    void action("compatibility", async () => {
      if (!model || !dataset) throw new Error("Upload a model and dataset first.");
      const report = await checkCompatibility(model.id, dataset.id);
      setReport(report);
      if (report.result === "PASSED") setNotice("Compatibility passed. You can start the evaluation.");
    });
  }

  function startEvaluation() {
    void action("evaluation", async () => {
      if (!model || !dataset || report?.result !== "PASSED") throw new Error("Run a passing compatibility check first.");
      const queued = await createEvaluation(model.id, dataset.id, taskType || undefined, workspace || undefined);
      navigate(`/evaluations/${queued.id}`);
    });
  }

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-8 text-slate-900">
      <div className="mx-auto min-w-0 max-w-3xl space-y-6 [overflow-wrap:anywhere]">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="text-xs uppercase tracking-[.18em] text-slate-500">Model evaluator</p><h1 className="text-3xl font-bold">New evaluation</h1></div>
          <div className="flex gap-3"><Link className="rounded border bg-white px-3 py-2" to="/history">History</Link>{["EVALUATOR", "ADMIN"].includes(currentRole() ?? "") && <Link className="rounded border bg-white px-3 py-2" to="/workspace">Workspace</Link>}<button className="rounded border bg-white px-3 py-2" onClick={async () => { try { await logout(); } finally { navigate("/login"); } }}>Log out</button></div>
        </header>
        {error && <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {notice && <p role="status" className="rounded bg-green-50 p-3 text-sm text-green-800">{notice}</p>}

        <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm">
          <div><p className="text-xs font-semibold tracking-widest text-emerald-700">01 / MODEL</p><h2 className="text-xl font-semibold">Upload trained model</h2><p className="text-sm text-slate-500">Scikit-learn or ONNX · up to 100 MB</p></div>
          <input className="max-w-full" aria-label="Model file" disabled={busy !== ""} type="file" accept=".pkl,.joblib,.onnx" onChange={(e) => chooseModel(e.target.files?.[0])} />
          {busy === "model" && <p role="status" className="text-sm">Uploading model…</p>}
          {model && <p className="text-sm text-green-700">Uploaded: {model.original_filename} · {model.id}</p>}
        </section>

        <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm">
          <div><p className="text-xs font-semibold tracking-widest text-emerald-700">02 / DATASET</p><h2 className="text-xl font-semibold">Upload test dataset</h2><p className="text-sm text-slate-500">UTF-8 CSV · up to 50 MB and 500,000 rows</p></div>
          <input className="max-w-full" aria-label="CSV dataset" disabled={busy !== ""} type="file" accept=".csv,text/csv" onChange={(e) => chooseDataset(e.target.files?.[0])} />
          {busy === "dataset" && <p role="status" className="text-sm">Uploading and validating dataset…</p>}
          {dataset && <div className="space-y-3 text-sm"><p className="text-green-700">Uploaded: {dataset.original_filename} · {dataset.row_count.toLocaleString()} rows · {dataset.columns.length} columns</p><label className="block font-medium">Target column<select className="mt-1 block w-full rounded border p-2" disabled={busy !== ""} value={target} onChange={(e) => changeTarget(e.target.value)}>{dataset.columns.map((column) => <option key={column} value={column}>{column}</option>)}</select></label></div>}
          {busy === "target" && <p role="status" className="text-sm">Saving target selection…</p>}
        </section>

        <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm">
          <div><p className="text-xs font-semibold tracking-widest text-emerald-700">03 / VALIDATE</p><h2 className="text-xl font-semibold">Check model compatibility</h2><p className="text-sm text-slate-500">Inspection uses the isolated sandbox.</p></div>
          <label className="block text-sm font-medium">Task type<select className="mt-1 block w-full rounded border p-2" value={taskType} onChange={(e) => setTaskType(e.target.value)}><option value="">Detect automatically</option><option value="CLASSIFICATION">Classification</option><option value="REGRESSION">Regression</option></select></label>
          <button disabled={busy !== "" || !model || !dataset || !target} className="rounded bg-emerald-800 px-4 py-2 font-semibold text-white disabled:opacity-50" onClick={runCompatibility}>{busy === "compatibility" ? "Checking…" : "Run compatibility check"}</button>
          {report && <div className={`rounded border p-4 ${report.result === "PASSED" ? "border-green-200 bg-green-50" : "border-amber-200 bg-amber-50"}`}><h3 className="font-semibold">{report.result === "PASSED" ? "Compatible" : "Compatibility failed"}</h3><p className="text-xs text-slate-600">Report {report.id}</p><ul className="mt-2 list-inside list-disc space-y-1 text-sm">{report.checks.map((check, i) => <li key={`${check.code}-${i}`}><strong>{check.code}:</strong> {check.message} <span className="text-slate-600">(expected {JSON.stringify(check.expected)}, got {JSON.stringify(check.actual)})</span></li>)}</ul></div>}
        </section>

        <section className="flex flex-col gap-3 rounded-xl bg-white p-6 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div><p className="text-xs font-semibold tracking-widest text-emerald-700">04 / RUN</p><h2 className="text-xl font-semibold">Evaluate model</h2><p className="text-sm text-slate-500">Trusted metrics are computed on the server.</p></div>
          <label className="text-sm">Share with workspace<select aria-label="Evaluation workspace" className="mt-1 block w-full rounded border p-2" value={workspace} disabled={busy !== ""} onChange={(e) => setWorkspace(e.target.value)}><option value="">Private evaluation</option>{workspaces.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <button disabled={busy !== "" || report?.result !== "PASSED"} className="rounded bg-blue-700 px-5 py-3 font-semibold text-white disabled:opacity-50" onClick={startEvaluation}>{busy === "evaluation" ? "Starting…" : "Start evaluation"}</button>
        </section>
        <p className="text-center text-xs text-slate-500">Uploaded pickle/joblib files are inspected and run only inside the isolated sandbox.</p>
      </div>
    </main>
  );
}
