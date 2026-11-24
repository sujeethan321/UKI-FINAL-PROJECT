// Purpose: Render the reusable api connection test interface and keep its presentation and interactions together.

import { useState } from "react";
import api from "../services/api";

// Render the api connection test interface and connect its controls to the state and callbacks defined here.
export default function ApiConnectionTest() {
  const [status, setStatus] = useState("Not tested");
  const [loading, setLoading] = useState(false);

  // Call the API health endpoint so the development screen can display connection status.
  const testConnection = async () => {
    setLoading(true);
    setStatus("Connecting...");

    try {
      const response = await api.get("/health");

      if (response.status === 200) {
        setStatus("Connected successfully!");
      }
    } catch {
      setStatus("Connection failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white p-8 rounded-xl shadow-md w-full max-w-md text-center">
        <h1 className="text-2xl font-bold text-slate-900 mb-3">
          LankaPex
        </h1>

        <p className="text-slate-500 mb-6">
          Frontend and Backend Connection Test
        </p>

        <button
          onClick={testConnection}
          disabled={loading}
          className="bg-teal-500 hover:bg-teal-600 text-white px-6 py-3 rounded-lg disabled:opacity-50"
        >
          {loading ? "Connecting..." : "Test API Connection"}
        </button>

        <p className="mt-5 font-medium text-slate-700">
          Status: {status}
        </p>
      </div>
    </div>
  );
}
