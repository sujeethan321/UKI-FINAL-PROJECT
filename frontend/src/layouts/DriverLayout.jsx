import LanguageSelector from "../components/LanguageSelector";
import { useAppTranslation } from "../i18n/useAppTranslation.js";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./driver.css";
import { useEffect,useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LogOut,Search,ChevronDown,UserRound } from "lucide-react";
import DriverSidebar from "../components/driver/DriverSidebar";
import NotificationBell from "../components/notifications/NotificationBell";
import { useAuth } from "../context/useAuth";

export default function DriverLayout() {
  const { tr } = useAppTranslation();
  const { user, logout } = useAuth();
  const [search,setSearch]=useState('');
  const location = useLocation(), navigate = useNavigate();
  useEffect(() => {
    if (["#driver-profile", "#active-deliveries"].includes(location.hash)) document.getElementById(location.hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [location.pathname, location.hash]);
  return <div className="driver-shell min-h-screen bg-[#F5F8FC] text-[#10243E] lg:flex">
    <DriverSidebar/>
    <div className="min-w-0 flex-1">
      <header className="sticky top-0 z-20 flex flex-wrap sm:flex-nowrap min-h-[80px] items-center justify-between gap-2 border-b border-[#E2EAF2] bg-white px-5 pl-20 sm:px-8 sm:pl-20 lg:px-10">
        <h1 className="sr-only">{location.pathname === "/driver/history" ? tr("Delivery History") : location.pathname === "/driver/deliveries" ? tr("My Deliveries") : location.pathname.startsWith("/driver/deliveries/") ? tr("Delivery Details") : location.pathname === "/driver/notifications" ? tr("Notifications") : location.pathname === "/driver/jobs" ? tr("Available Delivery Jobs") : ({"/driver/earnings":"My Earnings","/driver/vehicle":"My Vehicle","/driver/profile":"My Profile","/driver/settings":"Settings"}[location.pathname] || tr("Driver Dashboard"))}</h1>
        <form className="mr-2 flex basis-full sm:basis-auto min-w-0 flex-1 items-center gap-3 rounded-lg border border-[#DAE5F3] bg-[#F8FBFE] px-3 py-2.5" onSubmit={event=>{event.preventDefault();navigate('/driver/deliveries?q='+encodeURIComponent(search.trim()));}}><label className="sr-only" htmlFor="driver-header-search">{tr("Search current delivery page")}</label><Search size={21} className="shrink-0 text-[#52698A]" aria-hidden="true"/><input id="driver-header-search" type="search" maxLength={200} value={search} onChange={event=>setSearch(event.target.value)} placeholder={tr("Search assigned deliveries...")} className="min-w-0 flex-1 bg-transparent text-sm outline-none"/><button className="hidden text-xs font-semibold text-[#008C87] sm:block" type="submit">{tr("Search")}</button></form>
        <div className="flex max-w-full flex-wrap items-center gap-2 sm:gap-4"><LanguageSelector /><NotificationBell/><details className="relative"><summary className="flex cursor-pointer list-none items-center gap-3 rounded-lg p-1"><span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#E2F8F4] font-bold text-[#087D78]">{user?.full_name?.trim().split(/\s+/).slice(0,2).map(part=>part[0]).join('')||<UserRound size={20}/>}</span><span className="hidden max-w-40 truncate text-sm font-semibold sm:block">{user?.full_name}</span><ChevronDown size={16} aria-hidden="true"/></summary><div className="absolute right-0 top-full z-30 mt-3 w-52 rounded-xl border border-[#DAE5F3] bg-white p-2 shadow-xl"><Link className="block rounded-lg px-3 py-2 text-sm" to="/driver/profile">{tr("My Profile")}</Link><Link className="block rounded-lg px-3 py-2 text-sm" to="/driver/settings">{tr("Settings")}</Link><button type="button" aria-label={tr("Log out")} onClick={()=>{logout();navigate('/login',{replace:true});}} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-[#DC4545]"><LogOut size={17}/>{tr("Log out")}</button></div></details><span className="hidden rounded-full bg-[#F5F8FC] px-3 py-2 text-xs text-[#64748B] xl:block" title={tr("Online/offline availability is not provided by the Driver API")}>{tr("Presence unavailable")}</span></div>
      </header>
      <main className="driver-main min-w-0 px-4 py-6 sm:px-6 lg:px-7"><Outlet /></main>
    </div>
  </div>;
}
