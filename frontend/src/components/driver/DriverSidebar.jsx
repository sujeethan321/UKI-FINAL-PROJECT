import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { LayoutDashboard, PackageSearch, Truck, History, Bell, UserRound, Settings, Menu, X } from "lucide-react";
import BrandLogo from "../BrandLogo";

export default function DriverSidebar() {
  const [open, setOpen] = useState(false);
  const dialog = useRef(null);
  useEffect(() => { if (open && !dialog.current.open) dialog.current.showModal(); }, [open]);
  function close() { dialog.current?.close(); setOpen(false); }
  const navigation = <div className="flex h-full flex-col bg-[#10243E] text-white">
    <div className="border-b border-white/10 px-6 pb-7 pt-9"><BrandLogo /><p className="mt-3 text-xs font-semibold tracking-wider text-[#12B8A6]">DRIVER</p></div>
    <nav aria-label="Driver navigation" className="flex-1 space-y-1 overflow-y-auto px-4 py-6">
      <NavLink to="/driver/dashboard" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-[#176079] text-white" : "text-[#BED1DE] hover:bg-white/10")}><LayoutDashboard size={19} aria-hidden="true" />Dashboard</NavLink>
      <NavLink to="/driver/jobs" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-[#176079] text-white" : "text-[#BED1DE] hover:bg-white/10")}><PackageSearch size={19} aria-hidden="true" />Available Jobs</NavLink>
      <NavLink to="/driver/deliveries" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-[#176079] text-white" : "text-[#BED1DE] hover:bg-white/10")}><Truck size={19} aria-hidden="true" />My Deliveries</NavLink>
      <NavLink to="/driver/history" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-[#176079] text-white" : "text-[#BED1DE] hover:bg-white/10")}><History size={19} aria-hidden="true" />Delivery History</NavLink>
      <NavLink to="/driver/notifications" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-[#176079] text-white" : "text-[#BED1DE] hover:bg-white/10")}><Bell size={19} aria-hidden="true" />Notifications</NavLink>
      <Link to="/driver/dashboard#driver-profile" onClick={close} className="flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium text-[#BED1DE] hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-[#12B8A6]"><UserRound size={19} aria-hidden="true" />Profile</Link>
      {[["Settings", Settings]].map(([label, Icon]) => <div key={label} aria-disabled="true" className="flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-sm text-[#91A8BF]"><Icon size={19} aria-hidden="true" />{label}<span className="ml-auto text-xs">Planned</span></div>)}
    </nav>
    <p className="border-t border-white/10 px-6 py-5 text-xs text-[#91A8BF]">Business Connects Everyone</p>
  </div>;
  return <>
    <button type="button" aria-label="Open driver menu" aria-expanded={open} aria-controls="driver-mobile-sidebar" onClick={() => setOpen(true)} className="fixed left-4 top-4 z-40 flex h-11 w-11 items-center justify-center rounded-xl bg-[#10243E] text-white lg:hidden"><Menu size={23} /></button>
    <aside className="hidden h-screen w-[286px] shrink-0 lg:sticky lg:top-0 lg:block">{navigation}</aside>
    <dialog ref={dialog} id="driver-mobile-sidebar" aria-label="Driver menu" onClose={() => setOpen(false)} className="fixed inset-y-0 left-0 m-0 h-dvh max-h-none w-[min(286px,85vw)] max-w-none border-0 p-0 text-white backdrop:bg-[#10243E]/60">
      {navigation}<button type="button" aria-label="Close driver menu" onClick={close} className="absolute right-3 top-3 rounded-lg p-2 text-white focus-visible:outline-2 focus-visible:outline-[#12B8A6]"><X size={22} /></button>
    </dialog>
  </>;
}
