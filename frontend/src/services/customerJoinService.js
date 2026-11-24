// Purpose: Wrap customer join API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";

// Validate a path parameter before inserting it into an API URL.
const pathSegment = value => encodeURIComponent(String(value));
const publicCodePattern = /^[A-Za-z0-9_-]{32}$/;

// Call GET /customer/join-requests/by-code/{parameter} through the shared client so authentication and API configuration are applied consistently.
export async function getCustomerJoinRequestByCode(publicCode) {
  if (typeof publicCode !== "string" || !publicCodePattern.test(publicCode)) {
    throw new TypeError("Invalid shop code");
  }
  return (await api.get(`/customer/join-requests/by-code/${pathSegment(publicCode)}`)).data;
}

// Call GET /business-join/{parameter} through the shared client so authentication and API configuration are applied consistently.
export async function getBusinessJoinPreview(publicCode) {
  return (await api.get(`/business-join/${pathSegment(publicCode)}`)).data;
}

// Call POST /customer/join-requests through the shared client so authentication and API configuration are applied consistently.
export async function requestToJoinShop(publicCode) {
  return (await api.post("/customer/join-requests", { public_code: publicCode })).data;
}

// Call GET /customer/join-requests through the shared client so authentication and API configuration are applied consistently.
export async function getCustomerJoinRequests(page = 1, pageSize = 20) {
  return (await api.get("/customer/join-requests", {
    params: { page, page_size: pageSize },
  })).data;
}

// Call POST /customer/join-requests/{parameter}/cancel through the shared client so authentication and API configuration are applied consistently.
export async function cancelCustomerJoinRequest(requestId) {
  return (await api.post(`/customer/join-requests/${pathSegment(requestId)}/cancel`)).data;
}
