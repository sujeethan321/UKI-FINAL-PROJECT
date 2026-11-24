// Purpose: Compose the shop owner layout shell and nested screen area so related pages share navigation and presentation.
import useSubscription from '../hooks/useSubscription';
import { useAppTranslation } from "../i18n/useAppTranslation.js";

import { Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { getShopOwnerBusinessContext } from "../services/shopOwnerBusinessService";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./shopOwner.css";

import ShopOwnerSidebar from "../components/shopOwner/ShopOwnerSidebar";
import ShopOwnerHeader from "../components/shopOwner/ShopOwnerHeader";

const pageTitles = {
  "/shop-owner/dashboard": "Dashboard",
  "/shop-owner/customers": "Customers",
  "/shop-owner/products": "Shop & Products",
  "/shop-owner/credit-sales": "Credit Sales",
  "/shop-owner/repayments": "Repayments",
  "/shop-owner/credit-orders": "Credit Orders",
  "/shop-owner/deliveries": "Delivery Management",
  "/shop-owner/reports": "Reports",
  "/shop-owner/notifications": "Notifications",
  "/shop-owner/settings": "Settings",
  "/shop-owner/subscription": "Subscription & Billing",
  "/shop-owner/business/register": "Business Registration",
};

// Render the shop owner layout interface and connect its controls to the state and callbacks defined here.
export default function ShopOwnerLayout() {
  const { tr } = useAppTranslation();
  const { pathname } = useLocation();
  const [businesses, setBusinesses] = useState([]);
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => {
    let active = true;
    getShopOwnerBusinessContext().then(data => {
      if (active) setBusinesses(Array.isArray(data.businesses) ? data.businesses : []);
    }).catch(() => { if (active) setBusinesses([]); });
    return () => { active = false; };
  }, []);
  // Do not guess which business a page is operating on when several are linked.
  const business = businesses.length === 1 ? businesses[0] : null;

  const subscription=useSubscription(business?.business_id);
  const title = pathname.startsWith("/shop-owner/orders") ? "Orders" : pageTitles[pathname] ?? "Dashboard";

  return (
    <div className="shop-owner-shell min-h-screen bg-[#F5F8FC] lg:flex">
      {/* Shared sidebar */}
      <ShopOwnerSidebar entitlements={subscription.data?.entitlements} />

      {/* Main content area */}
      <div className="min-w-0 flex-1">
        {/* Shared top header */}
        <ShopOwnerHeader title={tr(title)} business={business} businessCount={businesses.length} />

        {/* Page-specific content */}
        <main className="shop-owner-main px-4 py-6 sm:px-6 lg:px-7">
          {pathname === '/shop-owner/dashboard' && <div className="owner-page-heading"><h2>{tr("Dashboard")}</h2><p>{tr("Your business at a glance")}</p></div>}
          <Outlet context={{businesses}} />
        </main>
      </div>
    </div>
  );
}
