import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createComparison, downloadReport, getHistory, type EvaluationStatus } from "../api/evaluations";
import { errorMessage } from "../api/errors";
import { currentRole } from "../api/client";

type Comparison = { id: string; evaluations: Array<{ id: string; task_type: string; model?: { filename?: string }; metrics: Record<string, unknown> }>; best_per_metric: Record<string, string> };

export default function History() {
  const [items, setItems] = useState<EvaluationStatus[]>([]);
  const [next, setNext] = useState(false);
  const [previous, setPrevious] = useState(false);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    getHistory(page).then((data) => {
      if (!active) return;
      setItems(data.results); setNext(!!data.next); setPrevious(!!data.previous);
    }).catch((cause) => active && setError(errorMessage(cause)));
    return () => { active = false; };
  }, [page]);

  async function compare() {
    setBusy(true); setError("");
    try { setComparison(await createComparison(selected) as Comparison); }
    catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  async function downloadComparison(format: "json" | "pdf") {
    if (!comparison) return;
    try { await downloadReport(`/comparisons/${comparison.id}/report.${format}`, `comparison-${comparison.id}.${format}`); }
    catch (cause) { setError(errorMessage(cause)); }
  }

  return <main className="min-h-screen bg-slate-100 px-4 py-8 text-slate-900"><div className="mx-auto max-w-5xl space-y-6">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs uppercase tracking-[.18em] text-slate-500">Private to your account</p><h1 className="text-3xl font-bold">Evaluation history</h1></div><div className="flex gap-2"><Link className="rounded border bg-white px-4 py-2" to="/upload">New evaluation</Link>{["EVALUATOR", "ADMIN"].includes(currentRole() ?? "") && <Link className="rounded border bg-white px-4 py-2" to="/workspace">Workspace</Link>}</div></header>
    {error && <p role="alert" className="rounded bg-red-50 p-3 text-red-700">{error}</p>}
    <section className="rounded-xl bg-white p-6 shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">Past runs</h2><p className="text-sm text-slate-500">Select 2–5 succeeded runs with the same dataset and task to compare.</p></div><button disabled={busy || selected.length < 2 || selected.length > 5} onClick={() => void compare()} className="rounded bg-emerald-800 px-4 py-2 text-white disabled:opacity-50">{busy ? "Comparing…" : `Compare selected (${selected.length})`}</button></div>
      <div className="mt-5 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr className="border-b text-xs uppercase text-slate-500"><th className="p-3">Select</th><th className="p-3">Run</th><th className="p-3">Task</th><th className="p-3">Status</th><th className="p-3">Created</th><th className="p-3">Result</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} className="border-b"><td className="p-3"><input type="checkbox" aria-label={`Select run ${item.id}`} disabled={item.status !== "SUCCEEDED" || (!selected.includes(item.id) && selected.length >= 5)} checked={selected.includes(item.id)} onChange={(e) => setSelected((ids) => e.target.checked ? [...ids, item.id] : ids.filter((id) => id !== item.id))}/></td><td className="p-3 font-mono text-xs">{item.id}</td><td className="p-3">{item.task_type ?? "—"}</td><td className="p-3"><span className="rounded-full bg-slate-100 px-2 py-1 text-xs">{item.status}</span></td><td className="p-3">{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</td><td className="p-3"><Link className="text-blue-700 underline" to={`/evaluations/${item.id}`}>Open</Link></td></tr>)}</tbody></table>{items.length === 0 && <p className="p-6 text-center text-slate-500">No evaluations found.</p>}</div>
      <div className="mt-4 flex justify-end gap-2"><button disabled={!previous || page <= 1} className="rounded border px-3 py-2 disabled:opacity-40" onClick={() => setPage((p) => p - 1)}>Previous</button><span className="px-3 py-2 text-sm">Page {page}</span><button disabled={!next} className="rounded border px-3 py-2 disabled:opacity-40" onClick={() => setPage((p) => p + 1)}>Next</button></div>
    </section>
    {comparison && <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">Comparison</h2><p className="text-sm text-slate-500">Best values are highlighted by the server comparison rules.</p></div><div className="flex gap-2"><button className="rounded border px-3 py-2" onClick={() => void downloadComparison("json")}>JSON</button><button className="rounded border px-3 py-2" onClick={() => void downloadComparison("pdf")}>PDF</button></div></div><div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr><th className="p-3">Metric</th>{comparison.evaluations.map((item, i) => <th key={item.id} className="p-3">{item.model?.filename ?? `Run ${i + 1}`}</th>)}</tr></thead><tbody>{Object.entries(comparison.best_per_metric).map(([metric, winner]) => <tr key={metric} className="border-t"><th className="p-3">{metric.replaceAll("_", " ")}</th>{comparison.evaluations.map((item) => <td key={item.id} className={`p-3 ${winner === item.id ? "font-bold text-emerald-800" : ""}`}>{String(item.metrics[metric] ?? "—")}{winner === item.id ? " · best" : ""}</td>)}</tr>)}</tbody></table></div></section>}
  </div></main>;
}
