// Purpose: Compose the customer layout shell and nested screen area so related pages share navigation and presentation.
import AccountMenu from "../components/ui/AccountMenu";
import LanguageSelector from "../components/LanguageSelector";
import { useAppTranslation } from "../i18n/useAppTranslation.js";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./customer.css";
import ShoppingProvider from "../context/ShoppingProvider";
import { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import CustomerSidebar from "../components/customer/CustomerSidebar";
import NotificationBell from "../components/notifications/NotificationBell";
import { useAuth } from "../context/useAuth";

// Render the customer layout interface and connect its controls to the state and callbacks defined here.
export default function CustomerLayout() {
  const { tr } = useAppTranslation();
  const { user, token, logout } = useAuth();
  const location = useLocation(), navigate = useNavigate();
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => {
    if (["#my-shops", "#my-credit", "#transactions"].includes(location.hash)) document.getElementById(location.hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [location.pathname, location.hash]);
  return <ShoppingProvider key={user?.user_id+":"+token}><div className="customer-shell min-h-screen bg-[#F5F8FC] text-[#10243E] lg:flex">
    <CustomerSidebar />
    <div className="min-w-0 flex-1">
      <header className="z-20 flex flex-wrap sm:flex-nowrap min-h-[80px] items-center justify-between gap-4 bg-transparent px-5 pl-20 sm:px-8 sm:pl-20 lg:px-10">
        <h1 className="sr-only">{location.pathname.startsWith("/customer/orders") ? tr("My Orders") : location.pathname === "/customer/cart" ? tr("Shopping Cart") : location.pathname === "/customer/checkout" ? tr("Checkout") : location.pathname === "/customer/shops/explore" ? tr("Explore Shops") : location.pathname.startsWith("/customer/explore/") ? (location.pathname.includes("/products/") ? tr("Product Details") : tr("Shop Catalogue")) : location.pathname === "/customer/notifications" ? tr("Notifications") : location.pathname === "/customer/shops" ? tr("My Shops") : location.pathname === "/customer/transactions" ? tr("Transaction History") : location.pathname.endsWith("/statement") ? tr("Credit Statement") : location.pathname.startsWith("/customer/credit/") ? tr("Credit Account Details") : tr("Customer Dashboard")}</h1>
        <div className="min-w-0 flex-1 py-4"><h2 className="break-words text-2xl font-bold">{tr("Welcome, {{name}}!", { name: user?.full_name || tr("Customer") })}</h2>{location.pathname === "/customer/dashboard" && <p className="mt-2 text-sm text-[#64748B]">{tr("Your credit and order overview.")}</p>}</div>
        <div className="flex max-w-full flex-wrap items-center gap-2 sm:gap-4"><LanguageSelector /><NotificationBell /><AccountMenu user={user} roleLabel="Customer" links={[{to:"/customer/profile",label:"My Profile"},{to:"/customer/settings",label:"Settings"}]} onLogout={()=>{logout();navigate('/login',{replace:true});}} /></div>
      </header>
      <main className="customer-main min-w-0 px-4 py-6 sm:px-6 lg:px-7"><Outlet /></main>
    </div>
  </div></ShoppingProvider>;
}
