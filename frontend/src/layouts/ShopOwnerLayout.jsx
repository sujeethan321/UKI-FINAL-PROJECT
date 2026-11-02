
import { Outlet, useLocation } from "react-router-dom";

import ShopOwnerSidebar from "../components/shopOwner/ShopOwnerSidebar";
import ShopOwnerHeader from "../components/shopOwner/ShopOwnerHeader";

const pageTitles = {
  "/shop-owner/dashboard": "Dashboard",
  "/shop-owner/customers": "Customers",
  "/shop-owner/products": "Products",
  "/shop-owner/credit-sales": "Credit Sales",
  "/shop-owner/repayments": "Repayments",
  "/shop-owner/credit-orders": "Credit Orders",
  "/shop-owner/deliveries": "Deliveries",
  "/shop-owner/reports": "Reports",
  "/shop-owner/notifications": "Notifications",
  "/shop-owner/settings": "Settings",
  "/shop-owner/business/register": "Business Registration",
};

export default function ShopOwnerLayout() {
  const { pathname } = useLocation();

  const title = pageTitles[pathname] ?? "Dashboard";

  return (
    <div className="min-h-screen bg-[#F5F8FC] lg:flex">
      {/* Shared sidebar */}
      <ShopOwnerSidebar />

      {/* Main content area */}
      <div className="min-w-0 flex-1">
        {/* Shared top header */}
        <ShopOwnerHeader title={title} />

        {/* Page-specific content */}
        <main className="px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
