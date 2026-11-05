
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

export function getDashboardPath(role) {
  return Object.hasOwn(roleRoutes, role) ? roleRoutes[role] : "/login";
}

export function getLoginPath(role) {
  return Object.hasOwn(loginRoutes, role) ? loginRoutes[role] : "/login";
}
