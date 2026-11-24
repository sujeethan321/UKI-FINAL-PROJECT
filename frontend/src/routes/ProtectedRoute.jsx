// Purpose: Wait for session restoration and redirect unsigned, inactive, or wrong-role users before rendering private screens; the API still enforces authorization.

import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../context/useAuth";
import {
  getDashboardPath,
  getLoginPath,
} from "../utils/roleRoutes";

// Gate private rendering by restored identity and role; backend authorization remains the final access check.
export default function ProtectedRoute({ allowedRoles }) {
  const { user, loading, isAuthenticated } = useAuth();

  // Wait until AuthContext finishes restoring the session.
  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#F5F8FC]">
        <p role="status" className="text-lg font-medium text-[#10243E]">
          Checking your LankaPex session...
        </p>
      </main>
    );
  }

  // No authenticated session.
  if (!isAuthenticated || !user) {
    const loginRole = allowedRoles?.[0];

    return (
      <Navigate
        to={getLoginPath(loginRole)}
        replace
      />
    );
  }

  // Unsupported or inactive identities never render a private route.
  if (user.account_status !== "active" || getDashboardPath(user.platform_role) === "/login") {
    return <Navigate to="/login" replace />;
  }

  // Valid session, but the wrong role.
  if (
    allowedRoles?.length &&
    !allowedRoles.includes(user.platform_role)
  ) {
    return (
      <Navigate
        to={getDashboardPath(user.platform_role)}
        replace
      />
    );
  }

  return <Outlet />;
}
