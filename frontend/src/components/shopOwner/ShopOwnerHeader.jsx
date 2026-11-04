
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronDown,
  LogOut,
  UserRound,
} from "lucide-react";

import NotificationBell from "../notifications/NotificationBell";

import { useAuth } from "../../context/useAuth";

export default function ShopOwnerHeader({
  title = "Dashboard",
}) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [menuOpen, setMenuOpen] = useState(false);

  const displayName = user?.full_name || "Shop Owner";

  const initials = displayName
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  function handleLogout() {
    setMenuOpen(false);
    logout();
    navigate("/login/shop-owner", {
      replace: true,
    });
  }

  return (
    <header className="relative z-20 flex min-h-[90px] items-center justify-between border-b border-[#E2EAF2] bg-white px-5 pl-20 sm:px-8 sm:pl-20 lg:px-10">
      {/* Page title */}
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-xl font-bold tracking-tight text-[#10243E] sm:text-2xl lg:text-3xl">
          {title}
        </h1>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-4">
      <NotificationBell />
      {/* Account menu */}
      <div className="relative">
        <button
          type="button"
          onClick={() => setMenuOpen((value) => !value)}
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          className="flex items-center gap-2 rounded-xl px-1 py-2 sm:gap-3 sm:px-2 text-[#10243E] transition hover:bg-[#F5F8FC]"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#E2F8F4] text-sm font-bold text-[#087D78]">
            {initials || <UserRound size={20} />}
          </div>

          <div className="hidden text-left sm:block">
            <p className="max-w-[170px] truncate text-sm font-semibold">
              {displayName}
            </p>
            <p className="text-xs text-[#64748B]">
              Shop Owner
            </p>
          </div>

          <ChevronDown
            size={17}
            className="hidden text-[#64748B] sm:block"
          />
        </button>

        {menuOpen && (
          <>
            {/* Dismiss menu when clicking outside */}
            <button
              type="button"
              aria-label="Close account menu"
              onClick={() => setMenuOpen(false)}
              className="fixed inset-0 z-20 cursor-default"
            />

            <div
              role="menu"
              aria-label="Account actions"
              className="absolute right-0 top-full z-30 mt-2 w-60 rounded-xl border border-[#DFE8F0] bg-white p-2 shadow-xl"
            >
              <div className="border-b border-[#E8EEF4] px-3 py-3">
                <p className="truncate text-sm font-semibold text-[#10243E]">
                  {displayName}
                </p>
                <p className="truncate text-xs text-[#64748B]">
                  {user?.email}
                </p>
              </div>

              <button
                type="button"
                role="menuitem"
                onClick={handleLogout}
                className="mt-2 flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm font-medium text-red-600 hover:bg-red-50"
              >
                <LogOut size={18} />
                Log Out
              </button>
            </div>
          </>
        )}
      </div>
      </div>
    </header>
  );
}
