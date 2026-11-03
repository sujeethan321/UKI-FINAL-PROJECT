import api from "./api";

export async function createShopOwnerCreditSale(businessId, payload) {
  const response = await api.post("/shop-owner/credit-sales", payload, {
    params: { business_id: businessId },
  });
  return response.data;
}
