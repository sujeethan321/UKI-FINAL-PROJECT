export function subscriptionDisplay(data, now = Date.now()) {
  const end = data?.trial_ends_at ? Date.parse(data.trial_ends_at) : 0;
  const seconds = Math.max(0, Math.ceil((end - now) / 1000));
  const active = Boolean(data?.trial_active && seconds > 0);
  return { active, days: Math.ceil(seconds / 86400),
    plan: data?.status === "TRIALING" && !active ? "FREE" : data?.effective_plan,
    upgrade: Boolean(data?.upgrade_required || (data?.status === "TRIALING" && !active)) };
}

export function formatPlanPrice(minor, language = "en") {
  if (!Number.isSafeInteger(minor) || minor < 0) return "—";
  const whole = Math.trunc(minor / 100), cents = String(minor % 100).padStart(2, "0");
  return `LKR ${new Intl.NumberFormat(language).format(whole)}${cents === "00" ? "" : `.${cents}`}`;
}
