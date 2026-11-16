import { getDashboardPath } from "./roleRoutes.js";

// A return destination is a path, never a URL or an arbitrary router state value.
export function validateJoinReturnPath(value) {
  if (typeof value !== "string") return null;
  const match = /^\/join\/([A-Za-z0-9_-]{32})$/.exec(value);
  return match ? `/join/${match[1]}` : null;
}

export function loginDestination(user, candidate) {
  const joinPath = validateJoinReturnPath(candidate);
  if (joinPath && user?.platform_role === "customer" && user?.account_status === "active") return joinPath;
  return getDashboardPath(user?.platform_role);
}

export function registrationLoginState(role, candidate) {
  const joinPath = validateJoinReturnPath(candidate);
  return role === "customer" && joinPath
    ? { registrationSuccess: true, joinReturnTo: joinPath }
    : { registrationSuccess: true };
}
