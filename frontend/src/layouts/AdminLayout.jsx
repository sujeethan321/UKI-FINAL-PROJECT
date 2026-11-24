// Purpose: Compose the admin layout shell and nested screen area so related pages share navigation and presentation.
import AccountMenu from "../components/ui/AccountMenu";
import LanguageSelector from "../components/LanguageSelector";
import { useAppTranslation } from "../i18n/useAppTranslation.js";

import { Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";

import NotificationBell from "../components/notifications/NotificationBell";

import AdminSidebar from "../components/admin/AdminSidebar.jsx";
import { useAuth } from "../context/useAuth";

// Render the admin layout interface and connect its controls to the state and callbacks defined here.
export default function AdminLayout() {
  const { tr } = useAppTranslation();
    const { pathname, hash } = useLocation();
    // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
    useEffect(() => {
        if (hash === '#recent-admin-activity') document.getElementById('recent-admin-activity')?.scrollIntoView();
    }, [pathname, hash]);
    const { user, logout } = useAuth();

    const title =
        pathname === "/admin/profile" ? "Personal Profile" : pathname === "/admin/notifications" ? "Notifications" : pathname === "/admin/businesses"
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
                        <AccountMenu user={user} roleLabel="Platform Admin" links={[{to:"/admin/profile",label:"Personal Profile"}]} onLogout={logout} />
                    </div>
                </header>

                <main className="px-5 py-7 sm:px-8 lg:px-10">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}
