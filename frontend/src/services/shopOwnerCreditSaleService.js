// Purpose: Wrap shop owner credit sale API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";

// Call POST /shop-owner/credit-sales through the shared client so authentication and API configuration are applied consistently.
export async function createShopOwnerCreditSale(businessId, payload) {
  const response = await api.post("/shop-owner/credit-sales", payload, {
    params: { business_id: businessId },
  });
  return response.data;
}
