// Purpose: Expose application-namespace translations through the shared i18n instance.
import { useTranslation } from "react-i18next";
import "./index.js";

// Natural English keys keep legacy labels/errors separate from business data.
// Only explicitly bound UI text is translated; unknown backend messages fall back.
export function useAppTranslation() {
  const { t, i18n } = useTranslation("application");
  // Translate application text through the application namespace with the wrapper fallback behavior.
  const tr = (key, values = {}) => typeof key === "string"
    ? t(key, { ...values, keySeparator: false, nsSeparator: false, defaultValue: key })
    : key ?? "";
  const labels = {submitted: "Submitted", processing: "Processing", "active":"Active","inactive":"Inactive","pending":"Pending","approved":"Approved","rejected":"Rejected","cancelled":"Cancelled","recorded":"Recorded","reversed":"Reversed","assigned":"Assigned","picked_up":"Picked up","in_transit":"In transit","delivered":"Delivered","completed":"Completed","confirmed":"Confirmed","closed":"Closed","suspended":"Suspended","reversal":"Reversal"};
  // Format status label for display so screens use a consistent representation.
  const statusLabel = value => Object.hasOwn(labels, value) ? tr(labels[value]) : value;
  return { tr, i18n, statusLabel };
}
