// Purpose: Configure the shared Axios client, attach access tokens, and propagate expired or changed browser sessions.

import axios from "axios";
import { validateApiUrl } from "../utils/apiConfig";

const TOKEN_KEY = "lankapex_access_token";
const SESSION_EXPIRED_EVENT = "lankapex:session-expired";
// Read the browser-wide token when checking whether a request still belongs to the current session.
const sharedToken = () => globalThis.localStorage?.getItem(TOKEN_KEY) ?? null;
let readAuthToken = sharedToken;
// Let the session provider supply the current token without creating a dependency from the HTTP client back to React.
export function setAuthTokenReader(reader) { readAuthToken = reader; }

// Validate the base URL once and bound request waiting so screens can recover from an unavailable API.
const api = axios.create({
  baseURL: validateApiUrl(import.meta.env.VITE_API_URL, import.meta.env.PROD),
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add the token to protected API requests automatically.
api.interceptors.request.use((config) => {
  const token = readAuthToken();
  const path = (config.url || "").split("?")[0];

  // Public authentication endpoints don't need a token.
  const isPublicAuthRequest =
    path === "/auth/login" ||
    path.startsWith("/auth/register/");

  // Stop an implicit-token request if another tab replaced the browser identity before this request was sent.
  if (!isPublicAuthRequest && !config.headers.has('Authorization') && token !== sharedToken()) {
    window.dispatchEvent(new Event('lankapex:session-changed'));
    throw new axios.CanceledError('Browser session changed; reload authorized context.');
  }

  if (token && !isPublicAuthRequest) {
    // Keep an explicitly supplied token, for example
    // one provided by getCurrentUser(token).
    if (!config.headers.has("Authorization")) {
      config.headers.set("Authorization", `Bearer ${token}`);
    }
  }

  return config;
});

// Detect rejected authenticated requests.
api.interceptors.response.use(
  (response) => response,

  (error) => {
    const status = error.response?.status;
    const authHeader =
      error.config?.headers?.get?.("Authorization");

    const storedToken = sharedToken();

    // Only clear a session when the failed request
    // actually used the token currently stored.
    if (
      status === 401 &&
      storedToken &&
      authHeader === `Bearer ${storedToken}`
    ) {
      localStorage.removeItem(TOKEN_KEY);

      window.dispatchEvent(
        new Event(SESSION_EXPIRED_EVENT)
      );
    }

    return Promise.reject(error);
  }
);

export default api;
