// Purpose: Expose the shared authentication context to components without duplicating session state.

import { useContext } from "react";
import { AuthContext } from "./AuthContext";

// Read the current authentication provider so consumers share the same verified session.
export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider"
    );
  }

  return context;
}
