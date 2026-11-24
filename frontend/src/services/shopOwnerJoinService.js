// Purpose: Wrap shop owner join API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";

// Validate a path parameter before inserting it into an API URL.
const pathSegment = value => encodeURIComponent(String(value));

// Call POST /shop-owner/businesses/{parameter}/join-link through the shared client so authentication and API configuration are applied consistently.
export async function getOrCreateBusinessJoinLink(businessId) {
  return (await api.post(`/shop-owner/businesses/${pathSegment(businessId)}/join-link`)).data;
}

// Call GET /shop-owner/businesses/{parameter}/join-requests through the shared client so authentication and API configuration are applied consistently.
export async function getBusinessJoinRequests(businessId, status, page = 1, pageSize = 20) {
  return (await api.get(`/shop-owner/businesses/${pathSegment(businessId)}/join-requests`, {
    params: { ...(status ? { status } : {}), page, page_size: pageSize },
  })).data;
}

// Call POST /shop-owner/businesses/{parameter}/join-requests/{parameter}/decision through the shared client so authentication and API configuration are applied consistently.
export async function decideBusinessJoinRequest(businessId, requestId, decision) {
  if (decision !== "approve" && decision !== "reject") {
    throw new TypeError("Decision must be approve or reject");
  }
  return (await api.post(
    `/shop-owner/businesses/${pathSegment(businessId)}/join-requests/${pathSegment(requestId)}/decision`,
    { decision },
  )).data;
}
