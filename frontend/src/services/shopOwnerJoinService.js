import api from "./api";

const pathSegment = value => encodeURIComponent(String(value));

export async function getOrCreateBusinessJoinLink(businessId) {
  return (await api.post(`/shop-owner/businesses/${pathSegment(businessId)}/join-link`)).data;
}

export async function getBusinessJoinRequests(businessId, status, page = 1, pageSize = 20) {
  return (await api.get(`/shop-owner/businesses/${pathSegment(businessId)}/join-requests`, {
    params: { ...(status ? { status } : {}), page, page_size: pageSize },
  })).data;
}

export async function decideBusinessJoinRequest(businessId, requestId, decision) {
  if (decision !== "approve" && decision !== "reject") {
    throw new TypeError("Decision must be approve or reject");
  }
  return (await api.post(
    `/shop-owner/businesses/${pathSegment(businessId)}/join-requests/${pathSegment(requestId)}/decision`,
    { decision },
  )).data;
}
