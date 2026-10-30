
export const roleRoutes = {
  shop_owner: "/shop-owner/dashboard",
  customer: "/customer/dashboard",
  driver: "/driver/dashboard",
  admin: "/admin/dashboard",
};

export const loginRoutes = {
  shop_owner: "/login/shop-owner",
  customer: "/login/customer",
  driver: "/login/driver",
  admin: "/login/admin",
};

export function getDashboardPath(role) {
  return roleRoutes[role] ?? "/select-role";
}

export function getLoginPath(role) {
  return loginRoutes[role] ?? "/select-role";
}
