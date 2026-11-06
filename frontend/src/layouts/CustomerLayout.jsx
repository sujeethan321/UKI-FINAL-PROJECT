import { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import CustomerSidebar from "../components/customer/CustomerSidebar";
import NotificationBell from "../components/notifications/NotificationBell";
import { useAuth } from "../context/useAuth";

export default function CustomerLayout() {
  const { user, logout } = useAuth();
  const location = useLocation(), navigate = useNavigate();
  useEffect(() => {
    if (["#my-shops", "#my-credit", "#transactions"].includes(location.hash)) document.getElementById(location.hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [location.pathname, location.hash]);
  return <div className="min-h-screen bg-[#F5F8FC] text-[#10243E] lg:flex">
    <CustomerSidebar />
    <div className="min-w-0 flex-1">
      <header className="relative z-20 flex min-h-[90px] items-center justify-between gap-2 border-b border-[#E2EAF2] bg-white px-5 pl-20 sm:px-8 sm:pl-20 lg:px-10">
        <h1 className="min-w-0 flex-1 truncate text-xl font-bold sm:text-2xl">{location.pathname === "/customer/notifications" ? "Notifications" : location.pathname === "/customer/shops" ? "My Shops" : location.pathname === "/customer/transactions" ? "Transaction History" : location.pathname.endsWith("/statement") ? "Credit Statement" : location.pathname.startsWith("/customer/credit/") ? "Credit Account Details" : "Customer Dashboard"}</h1>
        <div className="flex shrink-0 items-center gap-2 sm:gap-4"><NotificationBell /><div className="hidden sm:block"><p className="max-w-40 truncate text-sm font-semibold">{user?.full_name}</p><p className="text-xs text-[#64748B]">Customer</p></div><button type="button" aria-label="Log out" title="Log out" onClick={() => { logout(); navigate("/login", { replace: true }); }} className="rounded-lg p-2 text-[#64748B] hover:bg-red-50 hover:text-[#DC4545] focus-visible:outline-2 focus-visible:outline-[#12B8A6]"><LogOut size={20} /></button></div>
      </header>
      <main className="min-w-0 px-5 py-7 sm:px-8 lg:px-10"><Outlet /></main>
    </div>
  </div>;
}
