
import api from "./api";

// List businesses with an optional status filter and page window.
export async function getAdminBusinesses(
  status = "pending",
  { limit = 20, offset = 0, q, signal } = {}
) {
  const response = await api.get("/admin/businesses", {
    signal,
    params: {
      ...(status === "all" ? {} : { status }),
      limit,
      offset,
      ...(q ? { q } : {}),
    },
  });

  return response.data;
}

// Get business details and its linked owners.
export async function getAdminBusinessDetails(businessId, { signal } = {}) {
  const response = await api.get(
    `/admin/businesses/${businessId}`, { signal }
  );

  return response.data;
}

// Approve or reject a pending business.
export async function decideAdminBusiness(
  businessId,
  decision,
  reviewNote = null,
  { signal } = {}
) {
  if (!["approve", "reject"].includes(decision)) {
    throw new Error("Invalid business decision");
  }

  const response = await api.patch(
    `/admin/businesses/${businessId}/decision`,
    {
      decision,
      review_note: reviewNote,
    }, { signal }
  );

  return response.data;
}

// Retrieve the history of Admin approval decisions.
export async function getAdminBusinessAuditHistory(
  businessId,
  { signal, limit = 20, offset = 0 } = {}
) {
  const response = await api.get(
    `/admin/businesses/${businessId}/audit-history`, { signal, params: { limit, offset } }
  );

  return response.data;
}
