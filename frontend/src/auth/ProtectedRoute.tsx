import { Navigate, Outlet } from "react-router-dom";
import { isLoggedIn } from "../api/client";

export default function ProtectedRoute() {
  return isLoggedIn() ? <Outlet /> : <Navigate to="/login" replace />;
}