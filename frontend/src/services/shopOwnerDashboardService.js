
import api from "./api";

export async function getShopOwnerBusinessContext() {
  const response = await api.get(
    "/shop-owner/business-context"
  );

  return response.data;
}

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
