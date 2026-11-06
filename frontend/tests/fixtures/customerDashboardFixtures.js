export const transaction = (patch = {}) => ({ entry_id: 41, credit_account_id: 8, business_id: 2, business_name: "Linked Shop", entry_type: "credit_sale", recorded_at: "2026-11-06T10:00:00", amount: "100.25", balance_delta: "100.25", reference: "CS-test-reference", status: "recorded", ...patch });
export const fixtures = () => ({
  summary: { currency: "LKR", linked_shop_count: 1, credit_account_count: 1, total_outstanding_balance: "100.25", recent_activity: [transaction()] },
  shops: { currency: "LKR", total: 1, page: 1, page_size: 5, shops: [{ business_id: 2, business_name: "Linked Shop", credit_account_count: 1, outstanding_balance: "100.25" }] },
  accounts: { currency: "LKR", total: 1, page: 1, page_size: 5, credit_accounts: [{ credit_account_id: 8, business_id: 2, business_name: "Linked Shop", account_status: "active", credit_limit: "1000.00", outstanding_balance: "100.25", advance_balance: "0.00", available_credit: "899.75", opened_at: "2026-01-01T12:00:00" }] },
  transactions: { currency: "LKR", total: 1, page: 1, page_size: 5, transactions: [transaction()] },
});
