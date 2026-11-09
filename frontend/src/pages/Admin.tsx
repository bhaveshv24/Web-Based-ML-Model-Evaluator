import { useEffect, useState } from "react";
import { api, currentRole, json } from "../api/client";
import { errorMessage } from "../api/errors";

type Account = { id: string; email: string; role: string; is_active: boolean };
type Event = { id: number; event: string; actor_email: string; created_at: string };
type Page<T> = { results: T[]; next: string | null; previous: string | null };

export default function Admin() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [accounts, setAccounts] = useState<Page<Account> | null>(null);
  const [events, setEvents] = useState<Page<Event> | null>(null);
  const [eventPage, setEventPage] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [notice, setNotice] = useState("");
  const isAdmin = currentRole() === "ADMIN";

  useEffect(() => {
    if (!isAdmin) return;
    let active = true;
    Promise.all([
      api<Page<Account>>(`/admin/users?q=${encodeURIComponent(search)}&page=${page}`),
      api<Page<Event>>(`/admin/audit?page=${eventPage}`),
    ]).then(([users, audit]) => {
      if (active) { setAccounts(users); setEvents(audit); setError(""); }
    }).catch((cause) => { if (active) setError(errorMessage(cause)); });
    return () => { active = false; };
  }, [isAdmin, search, page, eventPage, revision]);

  async function toggle(account: Account) {
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/admin/users/${account.id}`, json("PATCH", { is_active: !account.is_active }));
      setNotice(`${account.email} ${account.is_active ? "deactivated" : "activated"}.`);
      setRevision((value) => value + 1);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  if (!isAdmin) return <main className="p-8"><h1>Administrator access required</h1></main>;
  return <main className="min-h-screen bg-slate-100 px-4 py-8 text-slate-900">
    <div className="mx-auto max-w-5xl space-y-6">
      <h1 className="text-3xl font-bold">Administration</h1>
      {error && <p role="alert" className="rounded bg-red-50 p-3 text-red-700">{error}</p>}
      {notice && <p role="status" className="rounded bg-green-50 p-3 text-green-800">{notice}</p>}
      <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">Accounts</h2>
        <form className="flex flex-wrap gap-3" onSubmit={(event) => {
          event.preventDefault(); setSearch(query); setPage(1);
        }}>
          <input aria-label="Search accounts" placeholder="Search by email" className="rounded border p-2" value={query} onChange={(event) => setQuery(event.target.value)} />
          <button className="rounded border px-4 py-2">Search</button>
        </form>
        <div className="overflow-x-auto"><table className="min-w-full text-left text-sm">
          <thead><tr><th className="p-2">Email</th><th className="p-2">Role</th><th className="p-2">Status</th><th className="p-2">Action</th></tr></thead>
          <tbody>{accounts?.results.map((account) => <tr key={account.id} className="border-t">
            <td className="p-2">{account.email}</td><td className="p-2">{account.role}</td>
            <td className="p-2">{account.is_active ? "Active" : "Inactive"}</td>
            <td className="p-2"><button disabled={busy} className="underline" onClick={() => void toggle(account)}>{account.is_active ? "Deactivate" : "Activate"}</button></td>
          </tr>)}</tbody>
        </table></div>
        {accounts?.results.length === 0 && <p>No matching accounts.</p>}
        <div className="flex gap-3"><button disabled={!accounts?.previous || busy} onClick={() => setPage(page - 1)}>Previous accounts</button><span>Page {page}</span><button disabled={!accounts?.next || busy} onClick={() => setPage(page + 1)}>Next accounts</button></div>
      </section>
      <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">Security audit</h2>
        <div className="overflow-x-auto"><table className="min-w-full text-left text-sm">
          <thead><tr><th className="p-2">Time</th><th className="p-2">Event</th><th className="p-2">Account</th></tr></thead>
          <tbody>{events?.results.map((event) => <tr key={event.id} className="border-t"><td className="p-2">{new Date(event.created_at).toLocaleString()}</td><td className="p-2">{event.event}</td><td className="p-2">{event.actor_email || "System"}</td></tr>)}</tbody>
        </table></div>
        <div className="flex gap-3"><button disabled={!events?.previous} onClick={() => setEventPage(eventPage - 1)}>Previous events</button><span>Page {eventPage}</span><button disabled={!events?.next} onClick={() => setEventPage(eventPage + 1)}>Next events</button></div>
      </section>
    </div>
  </main>;
}
