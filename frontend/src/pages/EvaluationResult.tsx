import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { errorMessage } from "../api/errors";
import { downloadReport, getEvaluation, getEvaluationStatus, type EvaluationDetail, type EvaluationStatus } from "../api/evaluations";

const active = (status: string) => status === "QUEUED" || status === "RUNNING";

export default function EvaluationResult() {
  const { id = "" } = useParams();
  const [run, setRun] = useState<EvaluationDetail | EvaluationStatus | null>(null);
  const [error, setError] = useState("");
  const [rocClass, setRocClass] = useState("");
  const timer = useRef<number>(0);
  const generation = useRef(0);

  useEffect(() => {
    const currentGeneration = ++generation.current;
    async function poll() {
      try {
        const status = await getEvaluationStatus(id);
        if (generation.current !== currentGeneration) return;
        setRun(status);
        if (status.status === "SUCCEEDED") {
          const detail = await getEvaluation(id);
          if (generation.current === currentGeneration) setRun(detail);
          return;
        }
        if (!active(status.status)) return;
        timer.current = window.setTimeout(poll, 2000);
      } catch (cause) {
        if (generation.current === currentGeneration) setError(errorMessage(cause));
      }
    }
    void poll();
    return () => { generation.current += 1; window.clearTimeout(timer.current); };
  }, [id]);

  const metrics = Object.entries((run as EvaluationDetail | null)?.metrics_json ?? {})
    .filter(([, value]) => value === null || ["string", "number", "boolean"].includes(typeof value));
  const charts = (run as EvaluationDetail | null)?.charts_json ?? {};
  const curveMap = charts.roc?.curves ?? {};
  const firstCurve = (Object.entries(curveMap).find(([label]) => label === rocClass) ?? Object.entries(curveMap)[0]) as [string, { fpr: number[]; tpr: number[]; auc: number }] | undefined;
  const rocPoints = firstCurve?.[1].fpr.map((fpr, index) => ({ fpr, tpr: firstCurve[1].tpr[index] })) ?? [];
  const scatter = charts.predicted_vs_actual;
  const scatterPoints = scatter?.actual?.map((actual: number, i: number) => ({ actual, predicted: scatter.predicted[i] })) ?? [];
  const residuals = charts.residuals;
  const residualPoints = residuals?.predicted?.map((predicted: number, i: number) => ({ predicted, residual: residuals.residual[i] })) ?? [];
  const histogram = charts.residual_histogram;
  const histogramPoints = histogram?.counts?.map((count: number, i: number) => ({ bin: histogram.edges[i], count })) ?? [];

  async function download(format: "json" | "pdf") {
    try { await downloadReport(`/evaluations/${id}/report.${format}`, `evaluation-${id}.${format}`); }
    catch (cause) { setError(errorMessage(cause)); }
  }

  return <main className="min-h-screen bg-slate-100 px-4 py-8 text-slate-900"><div className="mx-auto max-w-5xl space-y-6">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs uppercase tracking-[.18em] text-slate-500">Evaluation result</p><h1 className="text-3xl font-bold">{run?.status ?? "Loading"}</h1><p className="text-sm text-slate-600">{run?.task_type ?? "Preparing evaluation…"} · {id}</p></div><div className="flex gap-2"><Link className="rounded border bg-white px-4 py-2" to="/upload">New evaluation</Link><Link className="rounded border bg-white px-4 py-2" to="/history">History</Link></div></header>
    {error && <p role="alert" className="rounded bg-red-50 p-3 text-red-700">{error}</p>}
    {run && active(run.status) && <div role="status" className="rounded-xl bg-white p-6 shadow-sm"><p className="font-semibold">Evaluation {run.status.toLowerCase()}</p><p className="text-sm text-slate-600">This page checks the job status every two seconds.</p></div>}
    {run && (run.status === "FAILED" || run.status === "TIMED_OUT") && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6"><h2 className="font-semibold">Evaluation did not complete</h2><p>{run.error_code}: {run.error_message}</p></div>}
    {run?.status === "SUCCEEDED" && <>
      <section className="rounded-xl bg-white p-6 shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">Metrics</h2><p className="text-sm text-slate-500">Calculated by the trusted server-side metrics engine.</p></div><div className="flex gap-2"><button className="rounded bg-slate-800 px-4 py-2 text-white" onClick={() => void download("json")}>Download JSON</button><button className="rounded bg-slate-800 px-4 py-2 text-white" onClick={() => void download("pdf")}>Download PDF</button></div></div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{metrics.map(([key, value]) => <article key={key} className="rounded-lg border bg-slate-50 p-4"><p className="text-xs uppercase text-slate-500">{key.replaceAll("_", " ")}</p><strong className="mt-2 block text-xl">{typeof value === "number" ? Number(value.toPrecision(5)).toString() : String(value ?? "—")}</strong></article>)}</div>
      </section>
      {charts.confusion_matrix && <section className="rounded-xl bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Confusion matrix</h2><div className="mt-4 overflow-x-auto"><table className="min-w-full border-collapse text-sm"><thead><tr><th className="border p-2">Actual / predicted</th>{(charts.labels ?? []).map((label: string) => <th key={label} className="border p-2">{label}</th>)}</tr></thead><tbody>{charts.confusion_matrix.map((row: number[], i: number) => <tr key={charts.labels?.[i]}><th className="border p-2">{charts.labels?.[i]}</th>{row.map((value, j) => <td key={j} className="border p-2 text-center">{value}</td>)}</tr>)}</tbody></table></div></section>}
      {typeof (run as EvaluationDetail).metrics_json?.per_class === "object" && <section className="rounded-xl bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Per-class metrics</h2><div className="mt-4 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr><th className="p-2">Class</th><th className="p-2">Precision</th><th className="p-2">Recall</th><th className="p-2">F1</th><th className="p-2">Support</th></tr></thead><tbody>{Object.entries((run as EvaluationDetail).metrics_json?.per_class as Record<string, Record<string, number>>).map(([label, scores]) => <tr key={label} className="border-t"><th className="p-2">{label}</th><td className="p-2">{scores.precision}</td><td className="p-2">{scores.recall}</td><td className="p-2">{scores.f1}</td><td className="p-2">{scores.support}</td></tr>)}</tbody></table></div></section>}
      {rocPoints.length > 0 && <section className="rounded-xl bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">ROC curve{firstCurve ? ` · ${firstCurve[0]} · AUC ${firstCurve[1].auc.toFixed(3)}` : ""}</h2><label className="mt-3 block text-sm">ROC class<select className="ml-2 rounded border p-2" value={firstCurve?.[0] ?? ""} onChange={(e) => setRocClass(e.target.value)}>{Object.keys(curveMap).map((label) => <option key={label} value={label}>{label}</option>)}</select></label><div className="mt-4 h-72"><ResponsiveContainer width="100%" height="100%"><LineChart data={rocPoints}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="fpr" type="number" domain={[0, 1]} label={{ value: "False positive rate", position: "insideBottom", offset: -5 }}/><YAxis dataKey="tpr" type="number" domain={[0, 1]} label={{ value: "True positive rate", angle: -90, position: "insideLeft" }}/><Tooltip/><Line dataKey="tpr" stroke="#047857" dot={false}/></LineChart></ResponsiveContainer></div></section>}
      {scatterPoints.length > 0 && <section className="rounded-xl bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Predicted vs actual</h2><div className="mt-4 h-72"><ResponsiveContainer width="100%" height="100%"><ScatterChart><CartesianGrid/><XAxis dataKey="actual" name="Actual" type="number"/><YAxis dataKey="predicted" name="Predicted" type="number"/><Tooltip cursor={{ strokeDasharray: "3 3" }}/><Scatter data={scatterPoints} fill="#047857"/></ScatterChart></ResponsiveContainer></div></section>}
      {residualPoints.length > 0 && <section className="rounded-xl bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Residual plot</h2><div className="mt-4 h-72"><ResponsiveContainer width="100%" height="100%"><ScatterChart><CartesianGrid/><XAxis dataKey="predicted" name="Predicted" type="number"/><YAxis dataKey="residual" name="Residual" type="number"/><Tooltip/><Scatter data={residualPoints} fill="#b45309"/></ScatterChart></ResponsiveContainer></div></section>}
      {histogramPoints.length > 0 && <section className="rounded-xl bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Residual distribution</h2><div className="mt-4 h-72"><ResponsiveContainer width="100%" height="100%"><BarChart data={histogramPoints}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="bin"/><YAxis/><Tooltip/><Bar dataKey="count" fill="#047857"/></BarChart></ResponsiveContainer></div></section>}
    </>}
  </div></main>;
}
