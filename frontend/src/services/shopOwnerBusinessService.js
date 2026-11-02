
import api from "./api";

export async function createShopOwnerBusiness(payload) {
  const response = await api.post(
    "/shop-owner/businesses",
    payload
  );

  return response.data;
}

export async function getShopOwnerBusinessContext() {
  const response = await api.get(
    "/shop-owner/business-context"
  );

  return response.data;
}
