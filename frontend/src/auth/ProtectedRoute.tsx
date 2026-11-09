import { useEffect, useState } from "react";
import { Link, Navigate, Outlet, useNavigate } from "react-router-dom";
import { currentRole, isLoggedIn } from "../api/client";
import { logout } from "../api/auth";

export default function ProtectedRoute() {
  const [authenticated, setAuthenticated] = useState(isLoggedIn);
  const [ending, setEnding] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    const ended = () => setAuthenticated(false);
    window.addEventListener("session-ended", ended);
    return () => window.removeEventListener("session-ended", ended);
  }, []);
  if (!authenticated) return <Navigate to="/login" replace />;
  return <>
    <nav aria-label="Main navigation" className="flex flex-wrap items-center gap-4 border-b bg-white px-4 py-3 text-sm">
      <Link to="/upload" className="font-semibold text-emerald-800">Model evaluator</Link>
      <Link to="/history">History &amp; comparison</Link>
      {["EVALUATOR", "ADMIN"].includes(currentRole() ?? "") && <Link to="/workspace">Workspaces</Link>}
      {currentRole() === "ADMIN" && <Link to="/admin">Administration</Link>}
      <button disabled={ending} className="ml-auto underline" onClick={async () => {
        setEnding(true);
        try { await logout(); } finally { navigate("/login", { replace: true }); }
      }}>{ending ? "Signing out…" : "Sign out"}</button>
    </nav>
    <Outlet />
  </>;
}
