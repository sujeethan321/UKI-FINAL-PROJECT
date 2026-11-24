// Purpose: Render the reusable account menu interface and keep its presentation and interactions together.
import { Link } from "react-router-dom";
import { LogOut, Settings, UserRound } from "lucide-react";
import Dropdown from "./Dropdown";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";

// Render the account menu interface and connect its controls to the state and callbacks defined here.
export default function AccountMenu({ user, roleLabel, links = [], onLogout, logoutLabel = "Log out" }) {
  const { tr } = useAppTranslation();
  const name = user?.full_name || tr(roleLabel);
  const initials = name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
  return <Dropdown label={`${name} · ${tr("Account actions")}`} panelClassName="lp-account-menu"
    className="lp-account-trigger" trigger={<>
      <span className="lp-avatar" aria-hidden="true">{initials || <UserRound size={20} />}</span>
      <span className="lp-account-caption"><span>{name}</span><small>{tr(roleLabel)}</small></span>
    </>}>
    <div className="lp-menu-heading" role="presentation"><strong>{name}</strong>
      {user?.email && <span>{user.email}</span>}<small>{tr(roleLabel)}</small></div>
    {links.map(({ to, label }) => <Link key={to} to={to} role="menuitem" className="lp-menu-item">
      {label === "Settings" ? <Settings size={17} aria-hidden="true" /> : <UserRound size={17} aria-hidden="true" />}{tr(label)}
    </Link>)}
    <div className="lp-menu-separator" role="separator" />
    <button type="button" role="menuitem" className="lp-menu-item lp-menu-danger" onClick={onLogout}>
      <LogOut size={17} aria-hidden="true" />{tr(logoutLabel)}
    </button>
  </Dropdown>;
}
