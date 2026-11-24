// Purpose: Render the reusable shop owner sidebar interface and keep its presentation and interactions together.
import MobileNavigation from "../ui/MobileNavigation";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import BrandLogo from "../BrandLogo";

import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Package,
  CreditCard,
  Wallet,
  ShoppingCart,
  Truck,
  BarChart3,
  Bell,
  Settings,
  Menu,
  X,
  LockKeyhole,
} from "lucide-react";

const navigation = [
  {
    label: "Dashboard",
    path: "/shop-owner/dashboard",
    icon: LayoutDashboard,
    ready: true,
  },
  {
    label: "Customers",
    path: "/shop-owner/customers",
    icon: Users,
    ready: true,
  },
  {
    label: "Shop & Products",
    path: "/shop-owner/products",
    icon: Package,
    ready: true,
  },
  {
    label: "Credit Sales",
    path: "/shop-owner/credit-sales",
    icon: CreditCard,
    ready: true,
  },
  {
    label: "Repayments",
    path: "/shop-owner/repayments",
    icon: Wallet,
    ready: true,
  },
  {
    label: "Credit Orders",
    path: "/shop-owner/orders",
    icon: ShoppingCart,
    ready: true,
  },
  {
    label: "Deliveries",
    path: "/shop-owner/deliveries",
    icon: Truck,
    ready: true,
  },
  {
    label: "Reports",
    path: "/shop-owner/reports",
    icon: BarChart3,
    ready: true,
  },
  {
    label: "Notifications",
    path: "/shop-owner/notifications",
    icon: Bell,
    ready: true,
  },

  { label: "Support", path: "/shop-owner/support", icon: Bell, ready: true },
  {
    label: "Settings",
    path: "/shop-owner/settings",
    icon: Settings,
    ready: true,
  },
  {
    label: "Subscription & Billing",
    path: "/shop-owner/subscription",
    icon: CreditCard,
    ready: true,
  },
];

// Keep the reference order, with catalogue after delivery management.
const orderedNavigation = [navigation[0], navigation[1], navigation[3], navigation[4], navigation[5], navigation[6], navigation[2], ...navigation.slice(7)];

// Render the shop owner sidebar interface and connect its controls to the state and callbacks defined here.
export default function ShopOwnerSidebar({entitlements}) {
  const { tr } = useAppTranslation();
  const [isOpen, setIsOpen] = useState(false);

  // Close sidebar within the shop owner sidebar workflow.
  function closeSidebar() {
    setIsOpen(false);
  }

  const sidebar = (
    <div className="owner-sidebar flex h-full flex-col bg-[#10243E] text-white">
      {/* Logo and role */}
      <div className="owner-brand border-b border-white/10 px-6 py-7">
        <BrandLogo tone="dark" />
      </div>

      {/* Navigation */}
      <nav
        aria-label={tr("Shop owner navigation")}
        className="flex-1 space-y-1 overflow-y-auto px-4 py-6"
      >
        {orderedNavigation.map((item) => {
          const Icon = item.icon;

          if (!item.ready) {
            return (
              <div
                key={item.path}
                aria-disabled="true"
                title={`${item.label} — coming soon`}
                className="flex min-h-12 cursor-not-allowed items-center gap-3 rounded-xl px-4 py-3 text-[#91A8BF] opacity-70"
              >
                <Icon size={19} aria-hidden="true" />

                <span className="text-[15px] font-medium">
                  {tr(item.label)}
                </span>
              </div>
            );
          }

          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={closeSidebar}
              className={({ isActive }) =>
                [
                  "flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-medium transition-colors",
                  isActive
                    ? "bg-gradient-to-r from-[#12B8A6] to-[#007B91] text-white shadow-sm"
                    : "text-white hover:bg-white/10",
                ].join(" ")
              }
            >
              <Icon size={19} aria-hidden="true" />
              <span>{tr(item.label)}</span>{entitlements?.[{products:'catalogue',orders:'orders',deliveries:'deliveries',reports:'reports'}[item.path.split('/').at(-1)]]===false&&<LockKeyhole size={15} aria-label={tr('Upgrade to Pro')}/>}
            </NavLink>
          );
        })}
      </nav>

    </div>
  );

  return (
    <>
      {/* Mobile menu button */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label={tr("Open shop owner menu")}
        aria-expanded={isOpen}
        aria-controls="shop-owner-mobile-sidebar"
        className="fixed left-4 top-4 z-40 flex h-11 w-11 items-center justify-center rounded-xl bg-[#10243E] text-white shadow-lg lg:hidden"
      >
        <Menu size={23} />
      </button>

      {/* Desktop sidebar */}
      <aside className="hidden h-screen w-[286px] shrink-0 lg:sticky lg:top-0 lg:block">
        {sidebar}
      </aside>

      <MobileNavigation open={isOpen} onClose={closeSidebar} id="shop-owner-mobile-sidebar" label={tr("Shop owner navigation")}>
        {sidebar}
        <button type="button" onClick={closeSidebar} aria-label={tr("Close shop owner menu")}
          className="absolute right-3 top-3 rounded-lg p-2 text-white hover:bg-white/10"><X size={22} /></button>
      </MobileNavigation>
    </>
  );
}
