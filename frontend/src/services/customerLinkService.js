import api from './api';

export const createCustomerLinkInvitation = (businessId, customerId, recipientEmail) =>
  api.post(`/shop-owner/customers/${customerId}/link-invitations`,
    {recipient_email: recipientEmail}, {params: {business_id: businessId}}).then(response => response.data);

export const acceptCustomerLinkInvitation = invitation =>
  api.post('/customer/link-invitations/accept', {invitation}).then(response => response.data);
