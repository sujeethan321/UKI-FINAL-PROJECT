import { createContext, Fragment, useEffect, useState, useSyncExternalStore } from "react";
import { loginUser, getCurrentUser } from "../services/authService";
import { createAuthSession } from "../utils/authSession";

// Preserve the existing public context import used by consumers and tests.
// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session] = useState(() => createAuthSession({ loginUser, getCurrentUser, storage: () => sessionStorage }));
  const state = useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot);
  useEffect(() => {
    window.addEventListener("lankapex:session-expired", session.expire);
    session.restore();
    return () => {
      window.removeEventListener("lankapex:session-expired", session.expire);
      session.cancel();
    };
  }, [session]);
  return <AuthContext.Provider value={{ ...state, isAuthenticated: Boolean(state.user && state.token), login: session.login, logout: session.logout }}>
    <Fragment key={state.token || "signed-out"}>{children}</Fragment>
  </AuthContext.Provider>;
}
