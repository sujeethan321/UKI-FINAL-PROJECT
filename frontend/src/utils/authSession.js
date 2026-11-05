import { roleRoutes } from "./roleRoutes.js";

const TOKEN_KEY = "lankapex_access_token";

export function validateIdentity(user) {
  if (!user || !Number.isSafeInteger(user.user_id) || user.user_id <= 0 ||
      !Object.hasOwn(roleRoutes, user.platform_role) || user.account_status !== "active") {
    throw Object.assign(new Error("Unable to verify this account. Please sign in again."), { code: "INVALID_IDENTITY" });
  }
  return user;
}

// A generation invalidates every older request on logout or account switching.
export function createAuthSession({ loginUser, getCurrentUser, storage }) {
  let state = { user: null, token: null, loading: true };
  let generation = 0;
  let pendingLogin = null;
  const listeners = new Set();
  const publish = next => { state = next; listeners.forEach(listener => listener()); };
  const clear = () => storage().removeItem(TOKEN_KEY);
  const logout = () => {
    generation++;
    pendingLogin = null;
    try { clear(); } finally { publish({ user: null, token: null, loading: false }); }
  };
  const expire = () => {
    logout();
    publish({ ...state, notice: "Your session expired. Please sign in again." });
  };
  const restore = async () => {
    const attempt = ++generation;
    let notice = "";
    publish({ user: null, token: null, loading: true });
    try {
      const token = storage().getItem(TOKEN_KEY);
      if (!token) return;
      const user = validateIdentity(await getCurrentUser(token));
      if (attempt === generation) publish({ user, token, loading: false });
    } catch (error) {
      if (error?.response?.status === 401) notice = "Your session expired. Please sign in again.";
      if (attempt === generation) { try { clear(); } catch { /* Storage may be unavailable. */ } }
    } finally {
      if (attempt === generation && state.loading) publish({ user: null, token: null, loading: false, ...(notice ? { notice } : {}) });
    }
  };
  const login = (email, password) => {
    if (pendingLogin) return pendingLogin;
    const attempt = ++generation;
    publish({ user: null, token: null, loading: true });
    const operation = (async () => {
      try {
        clear();
        const response = await loginUser(email, password);
        if (attempt !== generation) throw new Error("Sign-in was cancelled.");
        if (typeof response?.access_token !== "string" || !response.access_token.trim()) throw new Error("Invalid sign-in response.");
        let user;
        try {
          user = validateIdentity(await getCurrentUser(response.access_token));
        } catch (error) {
          const verificationError = new Error("Unable to verify signed-in account.");
          verificationError.authStage = "identity";
          verificationError.response = error?.response ? { status: error.response.status } : undefined;
          verificationError.code = error?.code;
          throw verificationError;
        }
        if (attempt !== generation) throw new Error("Sign-in was cancelled.");
        storage().setItem(TOKEN_KEY, response.access_token);
        publish({ user, token: response.access_token, loading: false });
        return user;
      } catch (error) {
        if (attempt === generation) {
          try { clear(); } catch { /* Never retain an authenticated UI on storage failure. */ }
          publish({ user: null, token: null, loading: false });
        }
        throw error;
      }
    })();
    pendingLogin = operation;
    operation.finally(() => { if (pendingLogin === operation) pendingLogin = null; }).catch(() => {});
    return operation;
  };
  return {
    getSnapshot: () => state,
    subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); },
    login, logout, restore, expire,
    cancel: () => { generation++; pendingLogin = null; },
  };
}

export function getLoginErrorMessage(error) {
  const status = error?.response?.status;
  if (error?.authStage === "identity") {
    if (error.code === "INVALID_IDENTITY") return "Your account role could not be verified. Please contact your platform administrator.";
    if (status === 403) return "This account is not active. Please contact your platform administrator.";
    if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") return "Account verification timed out. Please try signing in again.";
    if (!error.response) return "Unable to verify your account. Check your connection and try signing in again.";
    return "Your sign-in could not be verified. Please sign in again.";
  }
  if (status === 401) return "Invalid email or password.";
  if (status === 403) return "This account is not active. Please contact your platform administrator.";
  if (status === 422) return "Enter a valid email address and password.";
  if (status === 429) return "Too many sign-in attempts. Please wait and try again.";
  if (error?.code === "ECONNABORTED" || error?.code === "ETIMEDOUT") return "The request timed out. Please try again.";
  if (!error?.response) return "Cannot reach the sign-in service. Check your connection and that the backend server is running.";
  return "Unable to sign in right now. Please try again later.";
}
