
import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Store,
  Users,
  Truck,
  Menu,
  X,
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
    icon: Users,
    enabled: false,
  },
  {
    label: "Customers",
    icon: Users,
    enabled: false,
  },
  {
    label: "Drivers",
    icon: Truck,
    enabled: false,
  },
];

export default function AdminSidebar() {
  const [open, setOpen] = useState(false);

  const menu = (
    <div className="flex h-full flex-col bg-[#10243E] text-white">
      <div className="border-b border-white/10 px-7 py-7">
        <h2 className="text-2xl font-bold">LankaPex</h2>
        <p className="mt-1 text-xs font-semibold tracking-widest text-[#12B8A6]">
          PLATFORM ADMIN
        </p>
      </div>

      <nav
        aria-label="Admin navigation"
        className="space-y-2 px-4 py-6"
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
                <Icon size={19} />
                {item.label}
                <span className="ml-auto text-[10px]">
                  Soon
                </span>
              </div>
            );
          }

          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition ${
                  isActive
                    ? "bg-[#176079] text-white"
                    : "text-[#D3E1EB] hover:bg-white/10"
                }`
              }
            >
              <Icon size={19} />
              {item.label}
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
        aria-label="Open admin menu"
        className="fixed left-4 top-5 z-40 rounded-lg bg-[#10243E] p-2 text-white lg:hidden"
      >
        <Menu size={22} />
      </button>

      <aside className="hidden h-screen w-[286px] shrink-0 lg:sticky lg:top-0 lg:block">
        {menu}
      </aside>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close admin menu"
            className="absolute inset-0 bg-black/50"
            onClick={() => setOpen(false)}
          />

          <aside className="absolute inset-y-0 left-0 w-[286px] max-w-[85vw]">
            {menu}

            <button
              type="button"
              aria-label="Close admin menu"
              onClick={() => setOpen(false)}
              className="absolute right-3 top-4 rounded-lg p-2 text-white"
            >
              <X size={20} />
            </button>
          </aside>
        </div>
      )}
    </>
  );
}
