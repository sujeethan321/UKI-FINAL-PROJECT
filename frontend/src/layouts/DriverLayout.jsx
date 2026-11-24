// Purpose: Compose the driver layout shell and nested screen area so related pages share navigation and presentation.
import AccountMenu from "../components/ui/AccountMenu";
import LanguageSelector from "../components/LanguageSelector";
import { useAppTranslation } from "../i18n/useAppTranslation.js";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./driver.css";
import { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import DriverSidebar from "../components/driver/DriverSidebar";
import NotificationBell from "../components/notifications/NotificationBell";
import { useAuth } from "../context/useAuth";

// Render the driver layout interface and connect its controls to the state and callbacks defined here.
export default function DriverLayout() {
  const { tr } = useAppTranslation();
  const { user, logout } = useAuth();
  const location = useLocation(), navigate = useNavigate();
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => {
    if (["#driver-profile", "#active-deliveries"].includes(location.hash)) document.getElementById(location.hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [location.pathname, location.hash]);
  return <div className="driver-shell min-h-screen bg-[#F5F8FC] text-[#10243E] lg:flex">
    <DriverSidebar/>
    <div className="min-w-0 flex-1">
      <header className="sticky top-0 z-20 flex flex-wrap sm:flex-nowrap min-h-[80px] items-center justify-end gap-2 border-b border-[#E2EAF2] bg-white px-5 pl-20 sm:px-8 sm:pl-20 lg:px-10">
        <h1 className="sr-only">{location.pathname === "/driver/history" ? tr("Delivery History") : location.pathname === "/driver/deliveries" ? tr("My Deliveries") : location.pathname.startsWith("/driver/deliveries/") ? tr("Delivery Details") : location.pathname === "/driver/notifications" ? tr("Notifications") : location.pathname === "/driver/jobs" ? tr("Available Delivery Jobs") : ({"/driver/earnings":"My Earnings","/driver/vehicle":"My Vehicle","/driver/profile":"My Profile","/driver/settings":"Settings"}[location.pathname] || tr("Driver Dashboard"))}</h1>
        <div className="flex max-w-full flex-wrap items-center gap-2 sm:gap-4"><LanguageSelector /><NotificationBell/><AccountMenu user={user} roleLabel="Driver" links={[{to:"/driver/profile",label:"My Profile"},{to:"/driver/settings",label:"Settings"}]} onLogout={()=>{logout();navigate('/login',{replace:true});}} /><span className="hidden rounded-full bg-[#F5F8FC] px-3 py-2 text-xs text-[#64748B] xl:block" title={tr("Online/offline availability is not provided by the Driver API")}>{tr("Presence unavailable")}</span></div>
      </header>
      <main className="driver-main min-w-0 px-4 py-6 sm:px-6 lg:px-7"><Outlet /></main>
    </div>
  </div>;
}
