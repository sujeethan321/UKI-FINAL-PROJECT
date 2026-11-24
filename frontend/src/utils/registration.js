// Purpose: Keep registration data handling and workflow helpers separate from React rendering so callers use consistent rules.
export const publicRegistrationRoles = ["shop-owner", "customer", "driver"];
// Create a blank form so opening a new operation does not reuse earlier input.
const emptyForm = () => ({ full_name: "", email: "", password: "", phone: "", preferred_language: "en" });

// Project registration form state into the payload expected by the selected account role.
export function registrationPayload(form, confirmation) {
  if (form.full_name.trim().length < 2 || form.full_name.trim().length > 150) throw new Error("Please enter your full name (2–150 characters).");
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()) || form.email.trim().length > 254) throw new Error("Please enter a valid email address.");
  if (form.password.length < 12 || form.password.length > 128 || new TextEncoder().encode(form.password).length > 1024) throw new Error("Password must contain 12–128 characters.");
  if (form.password !== confirmation) throw new Error("Passwords do not match.");
  if (form.phone.trim().length > 20) throw new Error("Phone number must contain at most 20 characters.");
  if (!["en", "ta", "si"].includes(form.preferred_language)) throw new Error("Please select a supported language.");
  return { full_name: form.full_name.trim(), email: form.email.trim().toLowerCase(), password: form.password, phone: form.phone.trim() || null, preferred_language: form.preferred_language };
}

// Create registration controller for the registration workflow.
export function createRegistrationController({ role = "shop-owner", services, onSuccess, errorMessage }) {
  // Create independent initial resource state so new readers do not inherit another instance state.
  const fresh = selected => ({ role: selected, form: emptyForm(), confirmPassword: "", loading: false, uncertain: false, error: "" });
  let state = fresh(publicRegistrationRoles.includes(role) ? role : "shop-owner");
  let generation = 0;
  let pending = null;
  const listeners = new Set();
  // Replace the store snapshot and notify subscribers so React can render the new state.
  const publish = next => { state = next; listeners.forEach(listener => listener()); };
  // Reset role within the registration workflow.
  const resetRole = role => {
    if (!publicRegistrationRoles.includes(role) || role === state.role) return false;
    generation++; pending = null; publish(fresh(role)); return true;
  };
  // Select role within the registration workflow.
  const selectRole = role => !state.loading && resetRole(role);
  // Apply the new state and notify the consumers or handlers registered by this workflow.
  const update = (name, value) => {
    if (state.loading) return;
    if (name === "confirmPassword") publish({ ...state, confirmPassword: value });
    else if (Object.hasOwn(state.form, name)) publish({ ...state, form: { ...state.form, [name]: value } });
  };
  // Submit the current form through its workflow and expose pending, success, or error state to the interface.
  const submit = () => {
    if (pending) return pending;
    if (state.uncertain) return Promise.resolve(false);
    let payload;
    try { payload = registrationPayload(state.form, state.confirmPassword); }
    catch (error) { publish({ ...state, error: error.message }); return Promise.resolve(false); }
    const selected = state.role;
    if (!publicRegistrationRoles.includes(selected) || typeof services[selected] !== "function") return Promise.resolve(false);
    const attempt = ++generation;
    publish({ ...state, loading: true, error: "" });
    const operation = Promise.resolve().then(() => attempt === generation ? services[selected](payload) : undefined).then(response => {
      if (attempt !== generation) return false;
      // Registration does not establish a session or alter approval status.
      publish(fresh(selected));
      onSuccess(response);
      return true;
    }).catch(error => {
      if (attempt === generation) {
        const uncertain = selected === 'driver' && (!error.response || error.response.status >= 500);
        publish({ ...state, loading: false, uncertain, error: uncertain ? 'Driver registration outcome is uncertain. Check sign-in or contact the operator before resubmitting.' : errorMessage(error) });
      }
      return false;
    }).finally(() => { if (pending === operation) pending = null; });
    pending = operation;
    return operation;
  };
  return {
    // Expose the current store snapshot to subscribers without starting a request.
    getSnapshot: () => state,
    // Register a state listener and return cleanup so consumers can unsubscribe.
    subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); },
    update, selectRole, resetRole, submit,
    // Cancel or invalidate pending work before this workflow is reset or unmounted.
    cancel: () => { generation++; pending = null; publish(fresh(state.role)); },
  };
}
