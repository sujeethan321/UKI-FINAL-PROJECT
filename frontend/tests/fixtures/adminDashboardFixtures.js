export const overviewFixture = () => ({ total_shop_owners: 12, total_customers: 30, total_drivers: 8, pending_driver_approvals: 3, approved_drivers: 5, total_businesses: 10, pending_business_approvals: 2, approved_businesses: 7, total_orders: 61, total_delivery_requests: 22 });
export const activityFixture = () => ({ total: 2, limit: 5, offset: 0, events: [
  { source: 'administrative', audit_id: 1, admin_user_id: 90, target_type: 'driver', target_id: 7, action: 'driver_approved', previous_state: 'pending', new_state: 'approved', reason: 'PRIVATE-NOTE', created_at: '2026-11-07T08:00:00' },
  { source: 'business_approval', audit_id: 1, admin_user_id: 90, target_type: 'business', target_id: 13, action: 'business_rejected', previous_state: 'pending', new_state: 'rejected', reason: 'PRIVATE-REASON', created_at: '2026-11-07T07:00:00' },
] });
