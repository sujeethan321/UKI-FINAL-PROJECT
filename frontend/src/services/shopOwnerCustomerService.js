// Purpose: Wrap shop owner customer API calls so components use a shared request interface instead of building HTTP requests themselves.

import api from "./api";

// Call GET /shop-owner/customers through the shared client so authentication and API configuration are applied consistently.
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

// Call POST /shop-owner/customers through the shared client so authentication and API configuration are applied consistently.
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

// Call GET /shop-owner/customers/{parameter} through the shared client so authentication and API configuration are applied consistently.
export async function getShopOwnerCustomerDetails(businessId, customerId, options = {}) {
  const response = await api.get(`/shop-owner/customers/${customerId}`, {
    params: { business_id: businessId },
    signal: options.signal,
  });
  return response.data;
}


// Call PATCH /shop-owner/customers/{parameter} through the shared client so authentication and API configuration are applied consistently.
export async function updateShopOwnerCustomer(businessId, customerId, payload) {
  const response = await api.patch(`/shop-owner/customers/${customerId}`, payload, {
    params: { business_id: businessId },
  });
  return response.data;
}

// Save shop owner credit account within the shop owner customer workflow.
export async function saveShopOwnerCreditAccount(businessId, customerId, payload, create) {
  const response = await api[create ? "post" : "patch"](
    `/shop-owner/customers/${customerId}/credit-account`, payload,
    { params: { business_id: businessId } },
  );
  return response.data;
}
