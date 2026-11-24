// Purpose: Wrap customer link API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';

// Call POST /shop-owner/customers/{parameter}/link-invitations through the shared client so authentication and API configuration are applied consistently.
export const createCustomerLinkInvitation = (businessId, customerId, recipientEmail) =>
  api.post(`/shop-owner/customers/${customerId}/link-invitations`,
    {recipient_email: recipientEmail}, {params: {business_id: businessId}}).then(response => response.data);

// Call POST /customer/link-invitations/accept through the shared client so authentication and API configuration are applied consistently.
export const acceptCustomerLinkInvitation = invitation =>
  api.post('/customer/link-invitations/accept', {invitation}).then(response => response.data);
