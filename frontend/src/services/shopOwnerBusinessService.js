// Purpose: Wrap shop owner business API calls so components use a shared request interface instead of building HTTP requests themselves.

import api from "./api";

// Call POST /shop-owner/businesses through the shared client so authentication and API configuration are applied consistently.
export async function createShopOwnerBusiness(payload) {
  const response = await api.post(
    "/shop-owner/businesses",
    payload
  );

  return response.data;
}

// Call GET /shop-owner/business-context through the shared client so authentication and API configuration are applied consistently.
export async function getShopOwnerBusinessContext() {
  const response = await api.get(
    "/shop-owner/business-context"
  );

  return response.data;
}
