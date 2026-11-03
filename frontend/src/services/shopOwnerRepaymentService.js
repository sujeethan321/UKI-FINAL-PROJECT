import api from "./api";

export async function createShopOwnerRepayment(businessId, payload) {
  const response = await api.post("/shop-owner/repayments", payload, {
    params: { business_id: businessId },
  });
  return response.data;
}
