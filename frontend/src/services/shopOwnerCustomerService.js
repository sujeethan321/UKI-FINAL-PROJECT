
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

export async function getShopOwnerCustomerDetails(businessId, customerId, options = {}) {
  const response = await api.get(`/shop-owner/customers/${customerId}`, {
    params: { business_id: businessId },
    signal: options.signal,
  });
  return response.data;
}


export async function updateShopOwnerCustomer(businessId, customerId, payload) {
  const response = await api.patch(`/shop-owner/customers/${customerId}`, payload, {
    params: { business_id: businessId },
  });
  return response.data;
}

export async function saveShopOwnerCreditAccount(businessId, customerId, payload, create) {
  const response = await api[create ? "post" : "patch"](
    `/shop-owner/customers/${customerId}/credit-account`, payload,
    { params: { business_id: businessId } },
  );
  return response.data;
}
