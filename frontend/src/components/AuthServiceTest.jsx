// Purpose: Render the reusable auth service test interface and keep its presentation and interactions together.

import { useState } from "react";

import {
  loginUser,
  getCurrentUser,
} from "../services/authService";

import { getApiErrorMessage } from "../utils/apiError";

// Render the auth service test interface and connect its controls to the state and callbacks defined here.
export default function AuthServiceTest() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

 
// Respond to the test login interaction using the current component state.
const handleTestLogin = async (event) => {
  event.preventDefault();

  setLoading(true);
  setError("");
  setResult(null);

  try {
    // Step 1: Verify login
    const loginData = await loginUser(email, password);

    console.log("Login request succeeded");

    // Step 2: Verify current user
    const user = await getCurrentUser(
      loginData.access_token
    );

    console.log("Current user request succeeded");

    setResult(user);

  } catch (err) {
    console.error("Request failed:", {
      url: err.config?.url,
      status: err.response?.status,
      code: err.code,
    });

    const endpoint = err.config?.url || "";

    if (endpoint.includes("/auth/me")) {
      setError(
        "Login succeeded, but retrieving user details failed."
      );
    } else {
      setError(getApiErrorMessage(err));
    }

  } finally {
    setLoading(false);
  }
};


  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <form
        onSubmit={handleTestLogin}
        className="w-full max-w-md bg-white shadow-lg rounded-2xl p-8 space-y-5"
      >
        <h1 className="text-2xl font-bold text-[#10243E]">
          LankaPex
        </h1>

        <p className="text-sm text-slate-500">
          Authentication Service Test
        </p>

        <input
          type="email"
          placeholder="Email address"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          className="w-full border rounded-lg p-3"
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          className="w-full border rounded-lg p-3"
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-[#12B8A6] text-white rounded-lg p-3 font-semibold disabled:opacity-50"
        >
          {loading ? "Testing..." : "Test Login"}
        </button>

        {error && (
          <p role="alert" className="text-red-600 text-sm">
            {error}
          </p>
        )}

        {result && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="font-semibold text-green-800">
              Authentication successful!
            </p>
            <p>Name: {result.full_name}</p>
            <p>Email: {result.email}</p>
            <p>Role: {result.platform_role}</p>
            <p>Status: {result.account_status}</p>
          </div>
        )}
      </form>
    </div>
  );
}
