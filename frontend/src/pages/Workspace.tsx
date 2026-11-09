import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, json, currentRole } from "../api/client";
import { errorMessage } from "../api/errors";

type WorkspaceRow = { id: string; name: string; member_count: number; created_at: string };
type WorkspaceRun = { id: string; status: string; task_type: string; created_at: string; owner_email?: string };

export default function Workspace() {
  const role = currentRole();
  const [items, setItems] = useState<WorkspaceRow[]>([]);
  const [selected, setSelected] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [runs, setRuns] = useState<WorkspaceRun[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [next, setNext] = useState(false);
  const [previous, setPrevious] = useState(false);
  const [runPage, setRunPage] = useState(1);
  const [nextRuns, setNextRuns] = useState(false);
  const [previousRuns, setPreviousRuns] = useState(false);

  useEffect(() => {
    if (role !== "EVALUATOR" && role !== "ADMIN") return;
    let mounted = true;
    api<{ results: WorkspaceRow[]; next: string | null; previous: string | null }>(`/workspaces?page=${page}`)
      .then((data) => {
        if (!mounted) return;
        const rows = data.results;
        setNext(!!data.next); setPrevious(!!data.previous);
        setItems(rows);
        setSelected((current) => current || rows[0]?.id || "");
      })
      .catch((cause) => mounted && setError(errorMessage(cause)));
    return () => { mounted = false; };
  }, [role, page]);

  async function submit(event: FormEvent, kind: "create" | "member") {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      if (kind === "create") {
        const created = await api<WorkspaceRow>("/workspaces", json("POST", { name }));
        setItems((rows) => [created, ...rows]); setSelected(created.id); setName(""); setNotice("Workspace created.");
      } else {
        await api(`/workspaces/${selected}/members`, json("POST", { email }));
        setItems((rows) => rows.map((row) => row.id === selected ? { ...row, member_count: row.member_count + 1 } : row));
        setEmail(""); setNotice("Workspace member added.");
      }
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  async function loadRuns(targetPage = 1) {
    setBusy(true); setError("");
    try {
      const data = await api<{ results: WorkspaceRun[]; next: string | null; previous: string | null }>(`/workspaces/${selected}/evaluations?page=${targetPage}`);
      setRuns(data.results ?? []);
      setRunPage(targetPage); setNextRuns(!!data.next); setPreviousRuns(!!data.previous);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  if (role !== "EVALUATOR" && role !== "ADMIN") return <main className="min-h-screen bg-slate-100 p-8"><div className="mx-auto max-w-2xl rounded-xl bg-white p-6"><h1 className="text-2xl font-bold">Evaluator access required</h1><p className="mt-2 text-slate-600">Workspace controls are limited to EVALUATOR and ADMIN accounts.</p><Link className="mt-4 inline-block text-blue-700 underline" to="/upload">Back to upload</Link></div></main>;

  return <main className="min-h-screen bg-slate-100 px-4 py-8 text-slate-900"><div className="mx-auto max-w-4xl space-y-6">
    <header className="flex items-center justify-between"><div><p className="text-xs uppercase tracking-[.18em] text-slate-500">{role} controls</p><h1 className="text-3xl font-bold">Workspaces</h1></div><Link className="rounded border bg-white px-4 py-2" to="/upload">New evaluation</Link></header>
    {error && <p role="alert" className="rounded bg-red-50 p-3 text-red-700">{error}</p>}{notice && <p role="status" className="rounded bg-green-50 p-3 text-green-800">{notice}</p>}
    <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Create workspace</h2><form className="flex flex-col gap-3 sm:flex-row" onSubmit={(e) => void submit(e, "create")}><input className="min-w-0 flex-1 rounded border p-2" aria-label="Workspace name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required/><button disabled={busy} className="rounded bg-emerald-800 px-4 py-2 text-white">Create</button></form></section>
    <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Manage members and view runs</h2><label className="block text-sm">Workspace<select disabled={busy} className="mt-1 block w-full rounded border p-2" value={selected} onChange={(e) => { setSelected(e.target.value); setRuns([]); setRunPage(1); setNextRuns(false); setPreviousRuns(false); }}><option value="">Choose workspace</option>{items.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.member_count} members</option>)}</select></label><div className="flex gap-3"><button disabled={!previous || busy} onClick={() => setPage(page - 1)}>Previous workspaces</button><span>Page {page}</span><button disabled={!next || busy} onClick={() => setPage(page + 1)}>Next workspaces</button></div>{selected && <><form className="flex flex-col gap-3 sm:flex-row" onSubmit={(e) => void submit(e, "member")}><input className="min-w-0 flex-1 rounded border p-2" type="email" aria-label="Member email" placeholder="Account email" value={email} onChange={(e) => setEmail(e.target.value)} required/><button disabled={busy} className="rounded border px-4 py-2">Add member</button></form><button disabled={busy} className="rounded border px-4 py-2" onClick={() => void loadRuns()}>Load workspace evaluations</button>{runs.length > 0 && <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr><th className="p-2">Evaluation</th><th className="p-2">Owner</th><th className="p-2">Task</th><th className="p-2">Status</th><th className="p-2">Created</th></tr></thead><tbody>{runs.map((run) => <tr key={run.id} className="border-t"><td className="p-2 font-mono text-xs"><Link className="text-blue-700 underline" to={`/evaluations/${run.id}`}>{run.id}</Link></td><td className="p-2">{run.owner_email}</td><td className="p-2">{run.task_type}</td><td className="p-2">{run.status}</td><td className="p-2">{new Date(run.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>}<div className="flex gap-3"><button disabled={!previousRuns || busy} onClick={() => void loadRuns(runPage - 1)}>Previous evaluations</button><span>Page {runPage}</span><button disabled={!nextRuns || busy} onClick={() => void loadRuns(runPage + 1)}>Next evaluations</button></div></>}</section>
  </div></main>;
}
