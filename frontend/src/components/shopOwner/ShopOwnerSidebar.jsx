
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
    label: "Products",
    path: "/shop-owner/products",
    icon: Package,
    ready: false,
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
    path: "/shop-owner/credit-orders",
    icon: ShoppingCart,
    ready: false,
  },
  {
    label: "Deliveries",
    path: "/shop-owner/deliveries",
    icon: Truck,
    ready: false,
  },
  {
    label: "Reports",
    path: "/shop-owner/reports",
    icon: BarChart3,
    ready: false,
  },
  {
    label: "Notifications",
    path: "/shop-owner/notifications",
    icon: Bell,
    ready: true,
  },
  {
    label: "Settings",
    path: "/shop-owner/settings",
    icon: Settings,
    ready: false,
  },
];

export default function ShopOwnerSidebar() {
  const [isOpen, setIsOpen] = useState(false);

  function closeSidebar() {
    setIsOpen(false);
  }

  const sidebar = (
    <div className="flex h-full flex-col bg-[#10243E] text-white">
      {/* Logo and role */}
      <div className="border-b border-white/10 px-6 pb-7 pt-9">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#12B8A6] text-xl font-bold">
            L
          </div>

          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              LankaPex
            </h1>

            <p className="mt-1 text-xs font-semibold tracking-wider text-[#6AE5D6]">
              SHOP OWNER
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav
        aria-label="Shop owner navigation"
        className="flex-1 space-y-1 overflow-y-auto px-4 py-6"
      >
        {navigation.map((item) => {
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
                  {item.label}
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
                    ? "bg-[#176079] text-white"
                    : "text-[#BED1DE] hover:bg-white/10 hover:text-white",
                ].join(" ")
              }
            >
              <Icon size={19} aria-hidden="true" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="border-t border-white/10 px-6 py-5">
        <p className="text-xs text-[#91A8BF]">
          LankaPex — Business Connects Everyone
        </p>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile menu button */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label="Open shop owner menu"
        aria-expanded={isOpen}
        className="fixed left-4 top-4 z-40 flex h-11 w-11 items-center justify-center rounded-xl bg-[#10243E] text-white shadow-lg lg:hidden"
      >
        <Menu size={23} />
      </button>

      {/* Desktop sidebar */}
      <aside className="hidden h-screen w-[286px] shrink-0 lg:sticky lg:top-0 lg:block">
        {sidebar}
      </aside>

      {/* Mobile sidebar */}
      {isOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close sidebar overlay"
            onClick={closeSidebar}
            className="absolute inset-0 bg-black/50"
          />

          <aside className="absolute inset-y-0 left-0 w-[min(286px,85vw)] shadow-2xl">
            {sidebar}

            <button
              type="button"
              onClick={closeSidebar}
              aria-label="Close shop owner menu"
              className="absolute right-3 top-3 rounded-lg p-2 text-white hover:bg-white/10"
            >
              <X size={22} />
            </button>
          </aside>
        </div>
      )}
    </>
  );
}
