// Purpose: Render the reusable select interface and keep its presentation and interactions together.
import "./dropdown.css";

// Preserve the native select contract: value, change events, labels, refs,
// validation, form submission, disabled options and keyboard/typeahead behavior.
export default function Select({ className = "", ...props }) {
  return <select {...props} className={`lp-select ${className}`} />;
}
