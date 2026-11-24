// Purpose: Wrap shop owner repayment API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";

// Call POST /shop-owner/repayments through the shared client so authentication and API configuration are applied consistently.
export async function createShopOwnerRepayment(businessId, payload) {
  const response = await api.post("/shop-owner/repayments", payload, {
    params: { business_id: businessId },
  });
  return response.data;
}
