import { Navigate, Outlet } from "react-router-dom";
import { Role, homeFor, useAuth } from "./AuthContext";
import { Spinner } from "../components/ui";

/** Frontend guard for UX only - the backend enforces authorization on every endpoint. */
export function ProtectedRoute({ roles }: { roles: Role[] }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10"><Spinner /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}
