import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { LayoutDashboard, Store, Compass, CreditCard, History, Truck, ShoppingBag, ShoppingCart, Bell, UserRound, Settings, Menu, X } from "lucide-react";
import BrandLogo from "../BrandLogo";

export default function CustomerSidebar() {
  const { tr } = useAppTranslation();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const dialog = useRef(null);
  useEffect(() => { if (open && !dialog.current.open) dialog.current.showModal(); }, [open]);
  function close() { dialog.current?.close(); setOpen(false); }
  const navigation = <div className="flex h-full flex-col bg-[#10243E] text-white">
    <div className="border-b border-white/10 px-6 pb-7 pt-9"><BrandLogo tone="dark" /></div>
    <nav aria-label={tr("Customer navigation")} className="flex-1 space-y-1 overflow-y-auto px-4 py-6">
      <NavLink to="/customer/dashboard" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white" : "text-white hover:bg-white/10")}><LayoutDashboard size={19} aria-hidden="true" />{tr("Dashboard")}</NavLink>
      <NavLink end to="/customer/shops" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white" : "text-white hover:bg-white/10")}><Store size={19} aria-hidden="true" />{tr("My Shops")}</NavLink>
      <NavLink to="/customer/shops/explore" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive || location.pathname.startsWith("/customer/explore/") ? "bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white" : "text-white hover:bg-white/10")}><Compass size={19} aria-hidden="true" />{tr("Browse Shops")}</NavLink>
      {[['My Orders','/customer/orders',ShoppingBag],['Shopping Cart','/customer/cart',ShoppingCart]].map(([label,to,Icon])=><NavLink key={to} to={to} onClick={close} className={({isActive})=>'flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] '+(isActive?'bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white':'text-white hover:bg-white/10')}><Icon size={19} aria-hidden="true"/>{tr(label)}</NavLink>)}
      <NavLink to="/customer/credit-accounts" onClick={close} className={({isActive})=>'flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium '+(isActive||location.pathname.startsWith('/customer/credit/')?'bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white':'text-white hover:bg-white/10')}><CreditCard size={19} aria-hidden="true"/>{tr("My Credit Accounts")}</NavLink>
      <NavLink to="/customer/deliveries" onClick={close} className={({isActive})=>'flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium '+(isActive?'bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white':'text-white hover:bg-white/10')}><Truck size={19} aria-hidden="true"/>{tr("My Deliveries")}</NavLink>
      <Link to="/customer/transactions?entry_type=repayment" onClick={close} className="flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium text-white hover:bg-white/10"><History size={19} aria-hidden="true"/>{tr("Repayments")}</Link>
      <NavLink to="/customer/transactions" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white" : "text-white hover:bg-white/10")}><History size={19} aria-hidden="true" />{tr("Transactions")}</NavLink>
      <NavLink to="/customer/notifications" onClick={close} className={({ isActive }) => "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-[#12B8A6] " + (isActive ? "bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white" : "text-white hover:bg-white/10")}><Bell size={19} aria-hidden="true" />{tr("Notifications")}</NavLink>
      {[["My Profile", "/customer/profile", UserRound], ["Settings", "/customer/settings", Settings]].map(([label,to,Icon])=><NavLink key={to} to={to} onClick={close} className={({isActive})=>'flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium '+(isActive?'bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white':'text-white hover:bg-white/10')}><Icon size={19} aria-hidden="true"/>{tr(label)}</NavLink>)}
    </nav>
  </div>;
  return <>
    <button type="button" aria-label={tr("Open customer menu")} aria-expanded={open} aria-controls="customer-mobile-sidebar" onClick={() => setOpen(true)} className="fixed left-4 top-4 z-40 flex h-11 w-11 items-center justify-center rounded-xl bg-[#10243E] text-white lg:hidden"><Menu size={23} /></button>
    <aside className="hidden h-screen w-[286px] shrink-0 lg:sticky lg:top-0 lg:block">{navigation}</aside>
    <dialog ref={dialog} id="customer-mobile-sidebar" aria-label={tr("Customer menu")} onClose={() => setOpen(false)} className="fixed inset-y-0 left-0 m-0 h-dvh max-h-none w-[min(286px,85vw)] max-w-none border-0 p-0 text-white backdrop:bg-[#10243E]/60">
      {navigation}<button type="button" aria-label={tr("Close customer menu")} onClick={close} className="absolute right-3 top-3 rounded-lg p-2 text-white focus-visible:outline-2 focus-visible:outline-[#12B8A6]"><X size={22} /></button>
    </dialog>
  </>;
}
