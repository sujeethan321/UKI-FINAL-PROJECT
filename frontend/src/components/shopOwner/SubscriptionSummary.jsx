// Purpose: Render the reusable subscription summary interface and keep its presentation and interactions together.
import { Link } from "react-router-dom";
import { useAppTranslation } from "../../i18n/useAppTranslation";
import useSubscription from "../../hooks/useSubscription";
import useTrialDisplay from "../../hooks/useTrialDisplay";

// Render the trial notice interface and connect its controls to the state and callbacks defined here.
export function TrialNotice({ data }) {
  const { tr, i18n } = useAppTranslation();
  const display = useTrialDisplay(data);
  const expiry = data?.trial_ends_at ? new Intl.DateTimeFormat(i18n.resolvedLanguage || "en", {
    dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Colombo" }).format(new Date(data.trial_ends_at)) : null;
  if (!display.active && !display.upgrade) return null;
  return <div className="subscription-trial" role="status">
    <strong>{tr(display.active ? "Your free Pro trial is active" : "Your Pro trial has ended")}</strong>
    <p>{display.active ? tr("{{days}} days remaining · Expires {{date}} (Sri Lanka time)", { days: display.days, date: expiry }) : tr("Free access is now active. Your records and repayment access are preserved.")}</p>
    <p>{tr("No card required. No automatic charge.")}</p>
  </div>;
}

// Render the subscription summary interface and connect its controls to the state and callbacks defined here.
export default function SubscriptionSummary({ businessId }) {
  const { tr } = useAppTranslation();
  const { data, error, loading, retry } = useSubscription(businessId);
  const display = useTrialDisplay(data);
  if (!businessId) return null;
  return <section className="rounded-2xl border border-[#D4E2EE] bg-white p-5 text-sm text-[#10243E]" aria-label={tr("Subscription & Billing")}>
    {loading ? <p role="status">{tr("Loading subscription...")}</p> : error ? <div role="alert"><p>{tr("Subscription access is unavailable. Refresh before trying again.")}</p><button type="button" className="mt-2 font-semibold text-[#087D78] underline" onClick={retry}>{tr("Retry")}</button></div> : <><p className="font-semibold">{tr("Current plan")}: {display.plan === "FREE" ? "Free" : display.plan === "PRO" ? "Pro" : "Business"}</p><TrialNotice data={data} /></>}
    <Link className="mt-3 inline-block font-semibold text-[#087D78] underline" to={`/shop-owner/subscription?business_id=${businessId}`}>{tr("Subscription & Billing")}</Link>
  </section>;
}
