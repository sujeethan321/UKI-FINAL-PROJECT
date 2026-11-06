import { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import DriverSidebar from "../components/driver/DriverSidebar";
import NotificationBell from "../components/notifications/NotificationBell";
import { useAuth } from "../context/useAuth";

export default function DriverLayout() {
  const { user, logout } = useAuth();
  const location = useLocation(), navigate = useNavigate();
  useEffect(() => {
    if (["#driver-profile", "#active-deliveries"].includes(location.hash)) document.getElementById(location.hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [location.pathname, location.hash]);
  return <div className="min-h-screen bg-[#F5F8FC] text-[#10243E] lg:flex">
    <DriverSidebar />
    <div className="min-w-0 flex-1">
      <header className="relative z-20 flex min-h-[90px] items-center justify-between gap-2 border-b border-[#E2EAF2] bg-white px-5 pl-20 sm:px-8 sm:pl-20 lg:px-10">
        <h1 className="min-w-0 flex-1 truncate text-xl font-bold sm:text-2xl">{location.pathname === "/driver/history" ? "Delivery History" : location.pathname === "/driver/deliveries" ? "My Deliveries" : location.pathname.startsWith("/driver/deliveries/") ? "Delivery Details" : location.pathname === "/driver/notifications" ? "Notifications" : location.pathname === "/driver/jobs" ? "Available Delivery Jobs" : "Driver Dashboard"}</h1>
        <div className="flex shrink-0 items-center gap-2 sm:gap-4"><NotificationBell /><div className="hidden sm:block"><p className="max-w-40 truncate text-sm font-semibold">{user?.full_name}</p><p className="text-xs text-[#64748B]">Driver</p></div><button type="button" aria-label="Log out" title="Log out" onClick={() => { logout(); navigate("/login", { replace: true }); }} className="rounded-lg p-2 text-[#64748B] hover:bg-red-50 hover:text-[#DC4545] focus-visible:outline-2 focus-visible:outline-[#12B8A6]"><LogOut size={20} /></button></div>
      </header>
      <main className="min-w-0 px-5 py-7 sm:px-8 lg:px-10"><Outlet /></main>
    </div>
  </div>;
}
