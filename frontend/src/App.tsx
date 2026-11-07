import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./auth/ProtectedRoute";

const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const Upload = lazy(() => import("./pages/Upload"));
const EvaluationResult = lazy(() => import("./pages/EvaluationResult"));
const History = lazy(() => import("./pages/History"));
const Workspace = lazy(() => import("./pages/Workspace"));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<p className="p-6 text-center text-slate-600">Loading workspace…</p>}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/upload" element={<Upload />} />
            <Route path="/evaluations/:id" element={<EvaluationResult />} />
            <Route path="/history" element={<History />} />
            <Route path="/workspace" element={<Workspace />} />
          </Route>
          <Route path="*" element={<Navigate to="/upload" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
