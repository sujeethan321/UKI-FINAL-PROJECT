export const publicRegistrationRoles = ["shop-owner", "customer", "driver"];
const emptyForm = () => ({ full_name: "", email: "", password: "", phone: "", preferred_language: "en" });

export function registrationPayload(form, confirmation) {
  if (form.full_name.trim().length < 2 || form.full_name.trim().length > 150) throw new Error("Please enter your full name (2–150 characters).");
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()) || form.email.trim().length > 254) throw new Error("Please enter a valid email address.");
  if (form.password.length < 12 || form.password.length > 128 || new TextEncoder().encode(form.password).length > 1024) throw new Error("Password must contain 12–128 characters.");
  if (form.password !== confirmation) throw new Error("Passwords do not match.");
  if (form.phone.trim().length > 20) throw new Error("Phone number must contain at most 20 characters.");
  if (!["en", "ta", "si"].includes(form.preferred_language)) throw new Error("Please select a supported language.");
  return { full_name: form.full_name.trim(), email: form.email.trim().toLowerCase(), password: form.password, phone: form.phone.trim() || null, preferred_language: form.preferred_language };
}

export function createRegistrationController({ role = "shop-owner", services, onSuccess, errorMessage }) {
  const fresh = selected => ({ role: selected, form: emptyForm(), confirmPassword: "", loading: false, error: "" });
  let state = fresh(publicRegistrationRoles.includes(role) ? role : "shop-owner");
  let generation = 0;
  let pending = null;
  const listeners = new Set();
  const publish = next => { state = next; listeners.forEach(listener => listener()); };
  const resetRole = role => {
    if (!publicRegistrationRoles.includes(role) || role === state.role) return false;
    generation++; pending = null; publish(fresh(role)); return true;
  };
  const selectRole = role => !state.loading && resetRole(role);
  const update = (name, value) => {
    if (state.loading) return;
    if (name === "confirmPassword") publish({ ...state, confirmPassword: value });
    else if (Object.hasOwn(state.form, name)) publish({ ...state, form: { ...state.form, [name]: value } });
  };
  const submit = () => {
    if (pending) return pending;
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
      if (attempt === generation) publish({ ...state, loading: false, error: errorMessage(error) });
      return false;
    }).finally(() => { if (pending === operation) pending = null; });
    pending = operation;
    return operation;
  };
  return {
    getSnapshot: () => state,
    subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); },
    update, selectRole, resetRole, submit,
    cancel: () => { generation++; pending = null; publish(fresh(state.role)); },
  };
}
