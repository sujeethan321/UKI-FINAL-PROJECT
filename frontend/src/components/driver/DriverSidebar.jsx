// Purpose: Render the reusable driver sidebar interface and keep its presentation and interactions together.
import MobileNavigation from "../ui/MobileNavigation";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useState } from "react";
import { NavLink } from "react-router-dom";
import { LayoutDashboard, Truck, History, Wallet, Bike, Bell, UserRound, Settings, Menu, X } from "lucide-react";
import BrandLogo from "../BrandLogo";

// Render the driver sidebar interface and connect its controls to the state and callbacks defined here.
export default function DriverSidebar() {
  const { tr } = useAppTranslation();
  const [open, setOpen] = useState(false);
  // Close the open interface and reset the state defined by this handler.
  function close() { setOpen(false); }
  const navigation = <div className="flex h-full flex-col bg-[#10243E] text-white">
    <div className="border-b border-white/10 px-6 pb-7 pt-9"><BrandLogo tone="dark" /></div>
    <nav aria-label={tr("Driver navigation")} className="flex-1 space-y-1 overflow-y-auto px-4 py-6">
      <NavLink to="/driver/dashboard" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white" : "text-white hover:bg-white/10")}><LayoutDashboard size={19} aria-hidden="true" />{tr("Dashboard")}</NavLink>
      <NavLink to="/driver/deliveries" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white" : "text-white hover:bg-white/10")}><Truck size={19} aria-hidden="true" />{tr("My Deliveries")}</NavLink>
      {[["My Earnings","/driver/earnings",Wallet],["My Vehicle","/driver/vehicle",Bike]].map(([label,to,Icon])=><NavLink key={to} to={to} onClick={close} className={({isActive})=>'flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium '+(isActive?'bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white':'text-white hover:bg-white/10')}><Icon size={19} aria-hidden="true"/>{tr(label)}</NavLink>)}
      <NavLink to="/driver/history" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white" : "text-white hover:bg-white/10")}><History size={19} aria-hidden="true" />{tr("Delivery History")}</NavLink>
      <NavLink to="/driver/notifications" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white" : "text-white hover:bg-white/10")}><Bell size={19} aria-hidden="true" />{tr("Notifications")}</NavLink>
      {[["My Profile","/driver/profile",UserRound],["Settings","/driver/settings",Settings]].map(([label,to,Icon])=><NavLink key={to} to={to} onClick={close} className={({isActive})=>'flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium '+(isActive?'bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white':'text-white hover:bg-white/10')}><Icon size={19} aria-hidden="true"/>{tr(label)}</NavLink>)}
      <NavLink to="/driver/support" onClick={close} className={({isActive})=>'flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium '+(isActive?'bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white':'text-white hover:bg-white/10')}><Bell size={19} aria-hidden="true"/>{tr("Support")}</NavLink>
    </nav>
  </div>;
  return <>
    <button type="button" aria-label={tr("Open driver menu")} aria-expanded={open} aria-controls="driver-mobile-sidebar" onClick={() => setOpen(true)} className="fixed left-4 top-4 z-40 flex h-11 w-11 items-center justify-center rounded-xl bg-[#10243E] text-white lg:hidden"><Menu size={23} /></button>
    <aside className="hidden h-screen w-[286px] shrink-0 lg:sticky lg:top-0 lg:block">{navigation}</aside>
    <MobileNavigation open={open} onClose={close} id="driver-mobile-sidebar" label={tr("Driver menu")}>
      {navigation}<button type="button" aria-label={tr("Close driver menu")} onClick={close} className="absolute right-3 top-3 rounded-lg p-2 text-white focus-visible:outline-2 focus-visible:outline-[#12B8A6]"><X size={22} /></button>
    </MobileNavigation>
  </>;
}
