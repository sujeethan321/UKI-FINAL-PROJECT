// Purpose: Connect the authentication session store to React and synchronize identity changes across requests and browser tabs.
import { createContext, Fragment, useEffect, useState, useSyncExternalStore } from "react";
import { loginUser, getCurrentUser } from "../services/authService";
import { browserLoginLock, createAuthSession, TOKEN_KEY, PROFILE_SIGNAL_KEY } from "../utils/authSession";
import i18n from '../i18n';
import { setAuthTokenReader } from '../services/api';

// Preserve the existing public context import used by consumers and tests.
// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext(null);

// Expose one session store to React and synchronize authentication with API requests and other tabs.
export function AuthProvider({ children }) {
  // Create the store once per provider mount so rerenders retain pending login and restoration state.
  const [session] = useState(() => createAuthSession({ loginUser, getCurrentUser, /* Resolve browser storage when needed instead of reading it during module initialization. */ storage: () => localStorage, withLoginLock: browserLoginLock }));
  // Subscribe to store snapshots rather than maintaining a second, potentially conflicting React session.
  const state = useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot);
  // Attach browser listeners for this mounted resource and remove them during effect cleanup.
  useEffect(() => {
    // Read the token at request time so Axios uses the same session identity as this provider.
    setAuthTokenReader(() => session.getSnapshot().token);
    window.addEventListener("lankapex:session-expired", session.expire);
    // Restore the shared session after a relevant storage or browser-session event.
    const synchronize = event => {
      if(event?.key===PROFILE_SIGNAL_KEY){void session.refreshIdentity().catch(()=>{});return;}
      // A null storage key means storage was cleared; unrelated storage entries do not require identity checks.
      if (!event || event.key === TOKEN_KEY || event.key === null) void session.restore();
    };
    window.addEventListener('storage', synchronize);
    window.addEventListener('lankapex:session-changed', synchronize);
    // Discard old per-tab authentication; never migrate competing tab accounts.
    try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* Legacy storage is never used for authentication. */ }
    session.restore();
    return () => {
      window.removeEventListener("lankapex:session-expired", session.expire);
      window.removeEventListener('storage', synchronize);
      window.removeEventListener('lankapex:session-changed', synchronize);
      // Invalidate pending identity responses before disconnecting this provider from the HTTP client.
      session.cancel();
      setAuthTokenReader(() => null);
    };
  }, [session]);
  useEffect(()=>{
    const language=state.user?.preferred_language;
    if(['en','ta','si'].includes(language))void i18n.changeLanguage(language);
  },[state.user?.preferred_language]);
  // Key the child tree by token so session changes remount private state instead of reusing another session's view.
  return <AuthContext.Provider value={{ ...state, isAuthenticated: Boolean(state.user && state.token), login: session.login, logout: session.logout, refreshIdentity: session.refreshIdentity, signalProfileChanged: session.signalProfileChanged }}>
    <Fragment key={state.token || "signed-out"}>{children}</Fragment>
  </AuthContext.Provider>;
}
