import LanguageSelector from "../components/LanguageSelector";
import { useAppTranslation } from "../i18n/useAppTranslation.js";

import { Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { LogOut, ShieldCheck } from "lucide-react";

import NotificationBell from "../components/notifications/NotificationBell";

import AdminSidebar from "../components/admin/AdminSidebar.jsx";
import { useAuth } from "../context/useAuth";

export default function AdminLayout() {
  const { tr } = useAppTranslation();
    const { pathname, hash } = useLocation();
    useEffect(() => {
        if (hash === '#recent-admin-activity') document.getElementById('recent-admin-activity')?.scrollIntoView();
    }, [pathname, hash]);
    const { user, logout } = useAuth();

    const title =
        pathname === "/admin/notifications" ? "Notifications" : pathname === "/admin/businesses"
            ? "Business Management"
            : ({ "/admin/shop-owners": "Shop Owner Management", "/admin/customers": "Customer Management", "/admin/drivers": "Delivery Driver Management" }[pathname] || "Platform Dashboard");

    return (
        <div className="min-h-screen bg-[#F5F8FC] lg:flex">
            <AdminSidebar />

            <div className="min-w-0 flex-1">
                <header className="relative z-20 flex min-h-[90px] items-center justify-between gap-3 border-b border-[#E2EAF2] bg-white px-5 pl-20 sm:px-8 sm:pl-20 lg:px-10">
                    <h1 className="min-w-0 flex-1 truncate text-xl font-bold text-[#10243E] sm:text-2xl">
                        {tr(title)}
                    </h1>

                    <div className="flex max-w-full flex-wrap items-center gap-3">
                        <LanguageSelector /><NotificationBell />
                        <ShieldCheck
                            size={22}
                            className="hidden text-[#12B8A6] sm:block"
                        />

                        <div className="hidden min-w-0 max-w-40 sm:block">
                            <p className="truncate text-sm font-semibold text-[#10243E]">
                                {user?.full_name || tr("Administrator")}
                            </p>
                            <p className="text-xs text-[#64748B]">{tr("Platform Admin")}</p>
                        </div>

                        <button
                            type="button"
                            onClick={logout}
                            aria-label={tr("Log out")}
                            title={tr("Log out")}
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
