import AccountMenu from "../ui/AccountMenu";
import LanguageSelector from "../LanguageSelector";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";

import { useNavigate } from "react-router-dom";
import {
  CalendarDays,
} from "lucide-react";

import NotificationBell from "../notifications/NotificationBell";

import { useAuth } from "../../context/useAuth";

export default function ShopOwnerHeader({
  title = "Dashboard",
  business,
  businessCount = 0,
}) {
  const { tr } = useAppTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();


  const displayName = user?.full_name || tr("Shop Owner");

  function handleLogout() {
    logout();
    navigate("/login/shop-owner", {
      replace: true,
    });
  }

  return (
    <header aria-label={tr("{{title}} workspace", { title: tr(title) })} className="sticky top-0 z-20 flex min-h-[102px] items-center justify-between gap-3 border-b border-[#E2EAF2] bg-white/95 px-5 pl-20 sm:px-7 sm:pl-20 lg:px-7">
      {/* Page title */}
      <div className="min-w-0 flex-1">
        <h1 className="sr-only">{tr(title)}</h1>
        <p className="text-xs text-[#52698A] sm:text-sm">{new Date().getHours() < 12 ? tr("Good Morning,") : new Date().getHours() < 18 ? tr("Good Afternoon,") : tr("Good Evening,")}</p>
        <p className="truncate text-lg font-bold tracking-tight text-[#10243E] sm:text-2xl">{displayName}</p>
        <p className="mt-1 truncate text-xs text-[#52698A] sm:text-sm">{business?.business_name || (businessCount > 1 ? tr("Your businesses") : tr("Shop Owner workspace"))}</p>
      </div>

      <div className="flex max-w-full flex-wrap items-center gap-2 sm:gap-4">
      <div className="hidden items-center gap-3 border-r border-[#E2EAF2] pr-5 text-sm text-[#52698A] xl:flex"><CalendarDays size={21} aria-hidden="true"/><time dateTime={new Date().toISOString()}>{new Intl.DateTimeFormat('en-LK',{day:'numeric',month:'short',year:'numeric'}).format(new Date())}</time></div>
      <LanguageSelector /><NotificationBell />
      <AccountMenu user={user} roleLabel="Shop Owner" onLogout={handleLogout} logoutLabel="Log Out" />
      </div>
    </header>
  );
}
