
import {
  createContext,
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  loginUser,
  getCurrentUser,
} from "../services/authService";

export const AuthContext = createContext(null);

const TOKEN_KEY = "lankapex_access_token";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  
useEffect(() => {
  function handleSessionExpired() {
    logout();
  }

  window.addEventListener(
    "lankapex:session-expired",
    handleSessionExpired
  );

  return () => {
    window.removeEventListener(
      "lankapex:session-expired",
      handleSessionExpired
    );
  };
}, [logout]);


  // Restore a session after a page refresh.
  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const storedToken = sessionStorage.getItem(TOKEN_KEY);

      if (!storedToken) {
        setLoading(false);
        return;
      }

      try {
        const currentUser = await getCurrentUser(storedToken);

        if (!cancelled) {
          setUser(currentUser);
          setToken(storedToken);
        }
      } catch {
        if (!cancelled) {
          logout();
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    restoreSession();

    return () => {
      cancelled = true;
    };
  }, [logout]);

  const login = async (email, password, expectedRole) => {
    const response = await loginUser(email, password);

    // Verify the signed token with the backend before
    // treating the user as authenticated.
    const currentUser = await getCurrentUser(
      response.access_token
    );

    // Check the role before saving the session.
    if (
      expectedRole &&
      currentUser.platform_role !== expectedRole
    ) {
      const error = new Error(
        "This account belongs to a different role. Please select the correct login page."
      );
      error.code = "ROLE_MISMATCH";
      throw error;
    }

    sessionStorage.setItem(
      TOKEN_KEY,
      response.access_token
    );

    setToken(response.access_token);
    setUser(currentUser);

    return currentUser;
  };

  const isAuthenticated = Boolean(user && token);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        isAuthenticated,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
