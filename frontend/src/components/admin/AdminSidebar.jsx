// Purpose: Render the reusable admin sidebar interface and keep its presentation and interactions together.
import MobileNavigation from "../ui/MobileNavigation";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import BrandLogo from "../BrandLogo";

import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Bell,
  LayoutDashboard,
  Store,
  Users,
  Truck,
  Menu,
  X,
  History,
  ChartNoAxesCombined,
} from "lucide-react";

const navigation = [
  {
    label: "Dashboard",
    path: "/admin/dashboard",
    icon: LayoutDashboard,
    enabled: true,
  },
  {
    label: "Business Management",
    path: "/admin/businesses",
    icon: Store,
    enabled: true,
  },
  {
    label: "Shop Owners",
    path: "/admin/shop-owners",
    icon: Users,
    enabled: true,
  },
  {
    label: "Customers",
    path: "/admin/customers",
    icon: Users,
    enabled: true,
  },
  {
    label: "Delivery Drivers",
    path: "/admin/drivers",
    icon: Truck,
    enabled: true,
  },
  { label: "Activity Logs", path: "/admin/dashboard#recent-admin-activity", icon: History, enabled: true },
  { label: "Platform Reports", path: "/admin/reports", icon: ChartNoAxesCombined, enabled: true },
  { label: "Support & Disputes", path: "/admin/support", icon: History, enabled: true },
  { label: "Notifications", path: "/admin/notifications", icon: Bell, enabled: true },
];

// Render the admin sidebar interface and connect its controls to the state and callbacks defined here.
export default function AdminSidebar() {
  const { tr } = useAppTranslation();
  const [open, setOpen] = useState(false);
  const { pathname, hash } = useLocation();
  // Close the open interface and reset the state defined by this handler.
  function close() { setOpen(false); }

  const menu = (
    <div className="flex h-full flex-col bg-[#10243E] text-white">
      <div className="relative border-b border-white/10 px-6 pb-7 pt-9">
        <BrandLogo tone="dark" />
        {/* Keep the role label inside the bottom padding so the logo area matches the Customer and Driver sidebars. */}
        <p className="absolute bottom-2 left-6 text-xs font-semibold tracking-widest text-[#12B8A6]">{tr("PLATFORM ADMIN")}</p>
      </div>

      <nav
        aria-label={tr("Admin navigation")}
        className="min-h-0 flex-1 space-y-2 overflow-y-auto px-4 py-6"
      >
        {navigation.map((item) => {
          const Icon = item.icon;

          if (!item.enabled) {
            return (
              <div
                key={item.label}
                className="flex cursor-not-allowed items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/40"
                aria-disabled="true"
              >
                <Icon size={19} aria-hidden="true" />
                {tr(item.label)}
                <span className="ml-auto text-[10px]">{tr("Soon")}</span>
              </div>
            );
          }

          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={close}
              aria-current={(item.path.includes('#') ? pathname + hash === item.path : pathname === item.path && !hash) ? 'page' : false}
              className={({ isActive }) =>
                `flex min-h-11 items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-[#12B8A6] ${
                  (item.path.includes('#') ? pathname + hash === item.path : isActive && !hash)
                    ? "bg-[#176079] text-white"
                    : "text-[#D3E1EB] hover:bg-white/10"
                }`
              }
            >
              <Icon size={19} aria-hidden="true" />
              {tr(item.label)}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={tr("Open admin menu")}
        aria-expanded={open}
        aria-controls="admin-mobile-sidebar"
        className="fixed left-4 top-5 z-40 flex h-11 w-11 items-center justify-center rounded-lg bg-[#10243E] text-white focus-visible:outline-2 focus-visible:outline-[#12B8A6] lg:hidden"
      >
        <Menu size={22} />
      </button>

      <aside className="hidden h-screen w-[286px] shrink-0 lg:sticky lg:top-0 lg:block">
        {menu}
      </aside>

      <MobileNavigation open={open} onClose={close} id="admin-mobile-sidebar" label={tr("Admin menu")}>
            {menu}

            <button
              type="button"
              aria-label={tr("Close admin menu")}
              onClick={close}
              className="absolute right-3 top-2 flex h-11 w-11 items-center justify-center rounded-lg text-white focus-visible:outline-2 focus-visible:outline-[#12B8A6]"
            >
              <X size={20} />
            </button>
      </MobileNavigation>
    </>
  );
}
