import api from "./api";

const pathSegment = value => encodeURIComponent(String(value));
const publicCodePattern = /^[A-Za-z0-9_-]{32}$/;

export async function getCustomerJoinRequestByCode(publicCode) {
  if (typeof publicCode !== "string" || !publicCodePattern.test(publicCode)) {
    throw new TypeError("Invalid shop code");
  }
  return (await api.get(`/customer/join-requests/by-code/${pathSegment(publicCode)}`)).data;
}

export async function getBusinessJoinPreview(publicCode) {
  return (await api.get(`/business-join/${pathSegment(publicCode)}`)).data;
}

export async function requestToJoinShop(publicCode) {
  return (await api.post("/customer/join-requests", { public_code: publicCode })).data;
}

export async function getCustomerJoinRequests(page = 1, pageSize = 20) {
  return (await api.get("/customer/join-requests", {
    params: { page, page_size: pageSize },
  })).data;
}

export async function cancelCustomerJoinRequest(requestId) {
  return (await api.post(`/customer/join-requests/${pathSegment(requestId)}/cancel`)).data;
}
