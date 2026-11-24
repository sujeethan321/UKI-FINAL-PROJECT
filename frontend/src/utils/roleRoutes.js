// Purpose: Keep role-to-dashboard and login routing decisions in one shared mapping.

export const roleRoutes = {
  shop_owner: "/shop-owner/dashboard",
  customer: "/customer/dashboard",
  driver: "/driver/dashboard",
  admin: "/admin/dashboard",
};

export const loginRoutes = {
  shop_owner: "/login",
  customer: "/login",
  driver: "/login",
  admin: "/login",
};

// Resolve the dashboard URL from the shared role map so navigation stays consistent with supported identities.
export function getDashboardPath(role) {
  return Object.hasOwn(roleRoutes, role) ? roleRoutes[role] : "/login";
}

// Resolve the login destination for the requested role so protected-route redirects use consistent URLs.
export function getLoginPath(role) {
  return Object.hasOwn(loginRoutes, role) ? loginRoutes[role] : "/login";
}
