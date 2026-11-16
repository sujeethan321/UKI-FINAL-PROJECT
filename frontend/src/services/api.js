
import axios from "axios";
import { validateApiUrl } from "../utils/apiConfig";

const TOKEN_KEY = "lankapex_access_token";
const SESSION_EXPIRED_EVENT = "lankapex:session-expired";

const api = axios.create({
  baseURL: validateApiUrl(import.meta.env.VITE_API_URL, import.meta.env.PROD),
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add the token to protected API requests automatically.
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const path = (config.url || "").split("?")[0];

  // Public authentication endpoints don't need a token.
  const isPublicAuthRequest =
    path === "/auth/login" ||
    path.startsWith("/auth/register/");

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

    const storedToken = sessionStorage.getItem(TOKEN_KEY);

    // Only clear a session when the failed request
    // actually used the token currently stored.
    if (
      status === 401 &&
      storedToken &&
      authHeader === `Bearer ${storedToken}`
    ) {
      sessionStorage.removeItem(TOKEN_KEY);

      window.dispatchEvent(
        new Event(SESSION_EXPIRED_EVENT)
      );
    }

    return Promise.reject(error);
  }
);

export default api;
