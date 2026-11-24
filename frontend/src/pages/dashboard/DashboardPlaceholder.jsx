// Purpose: Render the dashboard placeholder screen and connect its user interactions to shared application state and services.
import BrandLogo from "../../components/BrandLogo";

import { useNavigate } from "react-router-dom";
import { LogOut, ShieldCheck } from "lucide-react";

import { useAuth } from "../../context/useAuth";

const titles = {
  shop_owner: "Shop Owner Dashboard",
  customer: "Customer Dashboard",
  driver: "Delivery Driver Dashboard",
  admin: "Administrator Dashboard",
};

// Render the dashboard placeholder interface and connect its controls to the state and callbacks defined here.
export default function DashboardPlaceholder() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // Respond to the logout interaction using the current component state.
  function handleLogout() {
    logout();
    navigate("/select-role", { replace: true });
  }

  return (
    <main
      className={
        user?.platform_role === "shop_owner"
          ? "flex min-h-[360px] items-center justify-center"
          : "flex min-h-screen items-center justify-center bg-[#F5F8FC] p-6"
      }
    >
      <section className="w-full max-w-xl rounded-3xl border border-[#DCE8F0] bg-white p-8 text-center shadow-sm">
        <BrandLogo className="mx-auto mb-6" />
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-teal-50">
          <ShieldCheck
            size={32}
            className="text-[#12B8A6]"
          />
        </div>

        <h1 className="text-3xl font-bold text-[#10243E]">
          {titles[user?.platform_role] ?? "LankaPex Dashboard"}
        </h1>

        <p className="mt-4 text-[#526887]">
          Welcome, {user?.full_name}!
        </p>

        <p className="mt-2 text-sm text-[#526887]">
          Authenticated role: {user?.platform_role}
        </p>

        <div className="mt-7 rounded-xl bg-teal-50 p-4 text-sm font-medium text-teal-800">
          Your protected dashboard route is working.
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="mt-8 inline-flex items-center gap-2 rounded-xl bg-[#10243E] px-6 py-3 font-semibold text-white transition hover:bg-[#193754]"
        >
          <LogOut size={18} />
          Log Out
        </button>
      </section>
    </main>
  );
}
