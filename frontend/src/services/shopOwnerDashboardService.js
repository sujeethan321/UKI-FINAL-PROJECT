// Purpose: Wrap shop owner dashboard API calls so components use a shared request interface instead of building HTTP requests themselves.

import api from "./api";

// Call GET /shop-owner/business-context through the shared client so authentication and API configuration are applied consistently.
export async function getShopOwnerBusinessContext() {
  const response = await api.get(
    "/shop-owner/business-context"
  );

  return response.data;
}

// Call GET /shop-owner/dashboard/summary through the shared client so authentication and API configuration are applied consistently.
export async function getShopOwnerDashboardSummary(
  businessId
) {
  const response = await api.get(
    "/shop-owner/dashboard/summary",
    {
      params: {
        business_id: businessId,
      },
    }
  );

  return response.data;
}

// Call GET /shop-owner/dashboard/recent-transactions through the shared client so authentication and API configuration are applied consistently.
export async function getShopOwnerRecentTransactions(
  businessId
) {
  const response = await api.get(
    "/shop-owner/dashboard/recent-transactions",
    {
      params: {
        business_id: businessId,
      },
    }
  );

  return response.data;
}
