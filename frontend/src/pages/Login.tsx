import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../api/auth";
import { errorMessage } from "../api/errors";

export default function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      nav("/upload");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <form onSubmit={submit} className="w-96 bg-white p-8 rounded-xl shadow space-y-4">
        <h1 className="text-2xl font-bold">Sign in</h1>
        {error && <p role="alert" className="text-red-600 text-sm">{error}</p>}
        <input className="w-full border rounded p-2" type="email" placeholder="Email"
          value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input className="w-full border rounded p-2" type="password" placeholder="Password"
          value={password} onChange={(e) => setPassword(e.target.value)} required />
        <button disabled={busy}
          className="w-full bg-blue-600 text-white rounded p-2 disabled:opacity-50">
          {busy ? "Signing in..." : "Sign in"}
        </button>
        <p className="text-sm text-center">
          No account? <Link className="text-blue-600 underline" to="/register">Register</Link>
        </p>
      </form>
    </div>
  );
}