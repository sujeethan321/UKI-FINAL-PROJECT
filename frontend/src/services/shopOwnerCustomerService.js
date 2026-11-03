
import api from "./api";

export async function getShopOwnerCustomers(
  businessId,
  options = {}
) {
  const response = await api.get(
    "/shop-owner/customers",
    {
      params: {
        business_id: businessId,
      },
      signal: options.signal,
    }
  );

  return response.data;
}

export async function createShopOwnerCustomer(
  businessId,
  payload
) {
  const response = await api.post(
    "/shop-owner/customers",
    payload,
    {
      params: {
        business_id: businessId,
      },
    }
  );

  return response.data;
}
