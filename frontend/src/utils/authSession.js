// Purpose: Manage verified login, restoration, logout, and request generations so stale responses cannot replace the current identity.
import { roleRoutes } from "./roleRoutes.js";

export const TOKEN_KEY = "lankapex_access_token";
export const PROFILE_SIGNAL_KEY = 'lankapex_profile_changed';
// Create a distinct error when another account is already signed in to this browser.
const alreadySignedIn = () => Object.assign(new Error('Sign out of the existing account before signing in as another user.'), { code: 'BROWSER_ALREADY_SIGNED_IN' });

// Serialize login operations across tabs using an exclusive browser lock so competing logins cannot overwrite each other.
export function browserLoginLock(operation) {
  if (!globalThis.navigator?.locks?.request) return Promise.reject(Object.assign(new Error('Browser session locking is unavailable.'), {code:'BROWSER_SESSION_LOCK_UNAVAILABLE'}));
  return navigator.locks.request('lankapex:browser-login', {mode:'exclusive'}, operation);
}

// Accept only an active user with a supported role and valid identifier before publishing a signed-in session.
export function validateIdentity(user) {
  if (!user || !Number.isSafeInteger(user.user_id) || user.user_id <= 0 ||
      !Object.hasOwn(roleRoutes, user.platform_role) || user.account_status !== "active") {
    throw Object.assign(new Error("Unable to verify this account. Please sign in again."), { code: "INVALID_IDENTITY" });
  }
  return user;
}

// A generation invalidates every older request on logout or account switching.
export function createAuthSession({ loginUser, getCurrentUser, storage, withLoginLock = operation => operation() }) {
  let state = { user: null, token: null, loading: true };
  let generation = 0;
  let pendingLogin = null;
  let profileGeneration = 0;
  const listeners = new Set();
  // Replace the store snapshot and notify subscribers so React can render the new state.
  const publish = next => { state = next; listeners.forEach(listener => listener()); };
  // Remove the saved workflow value so it cannot be reused after reset.
  const clear = () => storage().removeItem(TOKEN_KEY);
  // Invalidate pending authentication work, remove the stored token, and publish the signed-out state.
  const logout = () => {
    generation++;
    pendingLogin = null;
    try { clear(); } finally { publish({ user: null, token: null, loading: false }); }
  };
  // Clear the rejected session and retain a notice explaining why the user must sign in again.
  const expire = () => {
    logout();
    publish({ ...state, notice: "Your session expired. Please sign in again." });
  };
  // Recheck the stored token against the API and publish a user only if this restoration attempt is still current.
  const restore = async () => {
    const attempt = ++generation;
    let notice = "";
    let restoredToken;
    publish({ user: null, token: null, loading: true });
    try {
      const token = storage().getItem(TOKEN_KEY);
      restoredToken = token;
      if (!token) return;
      const user = validateIdentity(await getCurrentUser(token));
      if (attempt === generation && storage().getItem(TOKEN_KEY) === token) publish({ user, token, loading: false });
    } catch (error) {
      if (error?.response?.status === 401) notice = "Your session expired. Please sign in again.";
      if (attempt === generation) { try { if (storage().getItem(TOKEN_KEY) === restoredToken) clear(); } catch { /* Storage may be unavailable. */ } }
    } finally {
      if (attempt === generation && state.loading) publish({ user: null, token: null, loading: false, ...(notice ? { notice } : {}) });
    }
  };
  // Refresh the same identity in place; never clear/remount the token on a profile save.
  const refreshIdentity = async () => {
    const token=state.token,previous=state.user,attempt=generation,profileAttempt=++profileGeneration;
    if(!token||!previous||storage().getItem(TOKEN_KEY)!==token)throw new Error('Browser session changed.');
    try {
      const user=validateIdentity(await getCurrentUser(token));
      if(attempt!==generation||profileAttempt!==profileGeneration||state.token!==token||storage().getItem(TOKEN_KEY)!==token)return null;
      if(user.user_id!==previous.user_id||user.platform_role!==previous.platform_role){expire();throw new Error('Profile identity changed; sign in again.');}
      publish({...state,user});return user;
    } catch(error) {
      if(attempt===generation&&state.token===token&&storage().getItem(TOKEN_KEY)===token&&([401,403].includes(error?.response?.status)||error?.code==='INVALID_IDENTITY'))expire();
      throw error;
    }
  };
  // Publish an opaque cross-tab signal so other views refresh profile identity without sharing profile contents.
  const signalProfileChanged = () => {
    if(state.token&&storage().getItem(TOKEN_KEY)===state.token){
      // A nonce only: never send tokens, profile fields or customer identifiers.
      try{storage().setItem(PROFILE_SIGNAL_KEY,globalThis.crypto.randomUUID());}catch{/* Other tabs can refresh manually when storage is blocked. */}
    }
  };
  // Verify the new token and account before publishing the session, with generation checks and cross-tab locking.
  const login = (email, password) => {
    if (pendingLogin) return pendingLogin;
    try {
      if (state.token || storage().getItem(TOKEN_KEY)) return Promise.reject(alreadySignedIn());
    } catch (error) { return Promise.reject(error); }
    const attempt = ++generation;
    publish({ user: null, token: null, loading: true });
    // Run the authentication attempt only while its generation remains current.
    const operation = (async () => {
      try {
        if (attempt !== generation) throw new Error('Sign-in was cancelled.');
        if (storage().getItem(TOKEN_KEY)) throw alreadySignedIn();
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
        if (storage().getItem(TOKEN_KEY)) throw alreadySignedIn();
        storage().setItem(TOKEN_KEY, response.access_token);
        publish({ user, token: response.access_token, loading: false });
        return user;
      } catch (error) {
        if (attempt === generation) {
          publish({ user: null, token: null, loading: false });
        }
        throw error;
      }
    });
    const locked = withLoginLock(operation).catch(error => {
      if (attempt === generation) publish({user:null,token:null,loading:false});
      throw error;
    });
    pendingLogin = locked;
    locked.finally(() => { if (pendingLogin === locked) pendingLogin = null; }).catch(() => {});
    return locked;
  };
  return {
    // Expose the current store snapshot to subscribers without starting a request.
    getSnapshot: () => state,
    // Register a state listener and return cleanup so consumers can unsubscribe.
    subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); },
    login, logout, restore, expire, refreshIdentity, signalProfileChanged,
    // Cancel or invalidate pending work before this workflow is reset or unmounted.
    cancel: () => { generation++; pendingLogin = null; },
  };
}

// Translate get login outcomes into display text for the interface.
export function getLoginErrorMessage(error) {
  if (error?.code === 'BROWSER_ALREADY_SIGNED_IN') return 'Sign out of the existing account before signing in as another user.';
  if (error?.code === 'BROWSER_SESSION_LOCK_UNAVAILABLE') return 'This browser cannot safely coordinate sign-in across tabs. Use a supported browser.';
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
