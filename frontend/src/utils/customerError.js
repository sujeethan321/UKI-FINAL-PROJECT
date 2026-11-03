// Only display expected API errors. Never render internal server diagnostics.
export function customerErrorMessage(error) {
  const status = error?.response?.status;
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You cannot manage customers for this business. Check your role and business approval.";
  if (status === 404) return "The customer or credit account was not found. Refresh customer data.";
  const detail = error?.response?.data?.detail;
  if (status === 409 || status === 422) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail.filter(item => typeof item?.msg === "string").map(item => {
        const field = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "Field";
        return `${field}: ${item.msg}`;
      });
      if (messages.length) return messages.join("; ");
    }
    return "Check your entries and refresh customer data before retrying.";
  }
  return "Unable to confirm changes. Refresh customer data before retrying.";
}
