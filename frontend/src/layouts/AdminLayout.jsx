
import { Outlet, useLocation } from "react-router-dom";
import { LogOut, ShieldCheck } from "lucide-react";

import AdminSidebar from "../components/admin/AdminSidebar.jsx";
import { useAuth } from "../context/useAuth";

export default function AdminLayout() {
    const { pathname } = useLocation();
    const { user, logout } = useAuth();

    const title =
        pathname === "/admin/businesses"
            ? "Business Management"
            : "Admin Dashboard";

    return (
        <div className="min-h-screen bg-[#F5F8FC] lg:flex">
            <AdminSidebar />

            <div className="min-w-0 flex-1">
                <header className="flex min-h-[90px] items-center justify-between gap-3 border-b border-[#E2EAF2] bg-white px-5 pl-20 sm:px-8 sm:pl-20 lg:px-10">
                    <h1 className="text-xl font-bold text-[#10243E] sm:text-2xl">
                        {title}
                    </h1>

                    <div className="flex items-center gap-3">
                        <ShieldCheck
                            size={22}
                            className="hidden text-[#12B8A6] sm:block"
                        />

                        <div className="hidden sm:block">
                            <p className="text-sm font-semibold text-[#10243E]">
                                {user?.full_name || "Administrator"}
                            </p>
                            <p className="text-xs text-[#64748B]">
                                Platform Admin
                            </p>
                        </div>

                        <button
                            type="button"
                            onClick={logout}
                            aria-label="Log out"
                            title="Log out"
                            className="rounded-lg p-2 text-[#64748B] hover:bg-red-50 hover:text-red-600"
                        >
                            <LogOut size={20} />
                        </button>
                    </div>
                </header>

                <main className="px-5 py-7 sm:px-8 lg:px-10">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}
