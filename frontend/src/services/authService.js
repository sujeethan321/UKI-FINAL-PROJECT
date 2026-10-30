
import api from "./api";

// Customer registration
export const registerCustomer = async (customerData) => {
  const response = await api.post(
    "/auth/register/customer",
    customerData
  );

  return response.data;
};

// Shop Owner registration
export const registerShopOwner = async (shopOwnerData) => {
  const response = await api.post(
    "/auth/register/shop-owner",
    shopOwnerData
  );

  return response.data;
};

// Delivery Driver registration
export const registerDriver = async (driverData) => {
  const response = await api.post(
    "/auth/register/driver",
    driverData
  );

  return response.data;
};

// Login with email and password

export const loginUser = async (email, password) => {
  const formData = new URLSearchParams();

  formData.append("username", email.trim().toLowerCase());
  formData.append("password", password);

  const response = await api.post(
    "/auth/login",
    formData,
    {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    }
  );

  return response.data;
};


// Retrieve the authenticated user
export const getCurrentUser = async (accessToken) => {
  const response = await api.get("/auth/me", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  return response.data;
};

