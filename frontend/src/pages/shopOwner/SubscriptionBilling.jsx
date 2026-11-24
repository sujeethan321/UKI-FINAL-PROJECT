// Purpose: Render the subscription billing screen and connect its user interactions to shared application state and services.
import { useEffect, useRef, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { useAppTranslation } from "../../i18n/useAppTranslation";
import Select from "../../components/ui/Select";
import { TrialNotice } from "../../components/shopOwner/SubscriptionSummary";
import useTrialDisplay from "../../hooks/useTrialDisplay";
import { formatPlanPrice } from "../../utils/subscription";
import useSubscription from "../../hooks/useSubscription";
import { getSubscriptionPlans, getSubscriptionHistory, createCheckout, createPortal, reconcileCheckout } from "../../services/subscriptionService";
import { billingRedirect, checkoutRequestKey } from "../../utils/billing";
import "./subscription.css";

const features = [['financial_history','Credit records & repayments'],['customers','Customer management'],['catalogue','Shop & product catalogue'],['orders','Customer Shopping Orders'],['deliveries','Delivery Management'],['reports','Detailed Reports'],['ai_summaries','AI Business Summaries'],['statement_exports','Export Statements'],['advanced_reports','Advanced Reports']];
// Check whether the current plan includes the requested feature before presenting its access state.
const included=(plan,key)=>key==='advanced_reports'?'Unavailable':plan?.entitlements?.[key]===true?'Included':plan?.entitlements?.[key]===false?'Locked':'Unavailable';

// Render the subscription billing view interface and connect its controls to the state and callbacks defined here.
export function SubscriptionBillingView({ businesses = [], businessId, onBusiness, data, plans = [],
  loading = false, error = false, history = null, onRetry, interval = "month", onInterval,
  busy = false, billingError = false, checkoutReturn, onCheckout, onPortal, onReconcile }) {
  const { tr, i18n } = useAppTranslation();
  const current = useTrialDisplay(data);
  return <div className="subscription-page">
    <div className="owner-page-heading"><h2>{tr("Subscription & Billing")}</h2><p>{tr("Choose a plan for each business. Keep your records and stay in control.")}</p></div>
    <label className="subscription-business">{tr("Business")}<Select disabled={busy} value={businessId || ""} onChange={event => onBusiness(Number(event.target.value))}>
      <option value="">{tr("Select business")}</option>{businesses.map(business => <option key={business.business_id} value={business.business_id}>{business.business_name}</option>)}</Select></label>
    {!businesses.length && <p>{tr("Register a business to view its subscription.")}</p>}
    {businessId && loading && <p role="status">{tr("Loading subscription...")}</p>}
    {error && <div className="subscription-error" role="alert"><p>{tr("Subscription access is unavailable. Refresh before trying again.")}</p><button type="button" onClick={onRetry}>{tr("Retry")}</button></div>}
    {businessId && data && <>
      {data.payment_configured && <p role="status">{tr("Stripe Sandbox — test payments only")}</p>}
      {checkoutReturn === 'success' && <p role="status">{tr("Checkout returned. Payment verification is pending; refresh subscription status.")}</p>}
      {checkoutReturn === 'cancelled' && <p role="status">{tr("Checkout cancelled. No plan change was confirmed.")}</p>}
      {data.payment_failed && <p role="alert">{tr("Payment failed. Update your payment method in Manage Subscription.")}</p>}
      {billingError && <p role="alert">{tr("Billing could not be confirmed. Reconcile the existing attempt before trying again.")}</p>}
      {busy && <p role="status">{tr("Contacting Sandbox billing...")}</p>}
      <section className="subscription-card"><p className="subscription-eyebrow">{tr("Current plan")}</p><h3>{current.plan === "PRO" ? "Pro" : current.plan === "BUSINESS" ? "Business" : "Free"}</h3><p>{tr(data.status === "ACTIVE" ? "Active subscription" : current.active ? "One calendar month of Pro, on us." : "Free access — no recurring payment.")}</p><TrialNotice data={data} /></section>
      <div className="subscription-interval" role="group" aria-label={tr("Billing interval")}>{[["month", "Monthly"], ["year", "Yearly"]].map(([value, label]) => <button key={value} type="button" aria-pressed={interval === value} onClick={() => onInterval(value)}>{tr(label)}</button>)}</div>
      <div className="subscription-plans">{plans.map(plan => <section className={`subscription-card ${plan.plan === current.plan ? "subscription-selected" : ""}`} key={plan.plan}>
        <div className="subscription-plan-heading"><h3>{plan.plan === "FREE" ? "Free" : plan.plan === "PRO" ? "Pro" : "Business"}</h3>{plan.plan === current.plan && <span>{tr("Current plan")}</span>}</div>
        <p className="subscription-price">{formatPlanPrice(interval === "year" ? plan.yearly_minor : plan.monthly_minor, i18n.resolvedLanguage || "en")}<small>{tr(plan.plan === "FREE" ? "forever" : interval === "year" ? "/ year" : "/ month")}</small></p>
        <p>{plan.customer_limit===null?tr('Unlimited credit customers'):plan.customer_limit===30?tr('Maximum 30 credit customers'):tr('Unavailable')}</p>
        <ul>{features.map(([key,label])=><li key={key}>{tr(label)}: {tr(included(plan,key))}</li>)}</ul>
        <p>{tr('AI rate limits apply per configured request window. Provider configuration is required.')}</p>
        <p>{tr('AI limit multiplier')}: {plan.ai_limit_multiplier ?? tr('Unavailable')}</p>
        <button type="button" disabled={!data.payment_configured || !data.checkout_available || busy || current.active || plan.plan === 'FREE' || (data.status === 'ACTIVE' && plan.plan === current.plan)} onClick={() => onCheckout?.(plan.plan)} aria-describedby="subscription-payment-note">{tr(plan.plan === current.plan ? "Current plan" : plan.plan === "FREE" ? "Free access after trial" : "Upgrade")}</button>
      </section>)}</div>
      <section className="subscription-card"><h3>{tr('Compare plan features')}</h3><p>{tr('Advanced Reports has no separate implemented module. Existing detailed reports are available on Pro and Business.')}</p><div className="subscription-table-wrap"><table><caption className="sr-only">{tr('Compare plan features')}</caption><thead><tr><th scope="col">{tr('Feature')}</th><th>Free</th><th>Pro</th><th>Business</th></tr></thead><tbody>{features.map(([key,label])=><tr key={key}><th scope="row">{tr(label)}</th>{['FREE','PRO','BUSINESS'].map(name=><td key={name}>{tr(included(plans.find(plan=>plan.plan===name),key))}</td>)}</tr>)}</tbody></table></div></section>
      <section className="subscription-card"><h3>{tr("Manage Subscription")}</h3><p id="subscription-payment-note">{tr(data.payment_configured ? "Paid billing starts only after your complimentary trial ends. No second trial is added." : "Payment integration not configured")}</p><p>{tr(data.payment_configured ? "Paid subscriptions renew automatically until cancelled in Manage Subscription." : "No card required. No automatic charge.")}</p><button type="button" disabled={!data.portal_available || busy} onClick={onPortal} aria-describedby="subscription-payment-note">{tr("Manage Subscription")}</button>
        <button type="button" disabled={busy} onClick={onRetry}>{tr("Refresh subscription")}</button>
        {data.payment_configured && <button type="button" disabled={busy} onClick={onReconcile}>{tr("Reconcile pending Checkout")}</button>}
      </section>
      <section className="subscription-card"><h3>{tr("Payment & invoice history")}</h3><p>{tr(history?.available ? "No invoices available." : data.payment_configured ? "View invoices in the hosted billing portal." : "Payment history is unavailable while payments are not configured.")}</p></section>
    </>}
  </div>;
}

// Render the subscription billing interface and connect its controls to the state and callbacks defined here.
export default function SubscriptionBilling() {
  const { businesses = [] } = useOutletContext() || {};
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get("business_id"));
  const businessId = businesses.find(business => business.business_id === requested)?.business_id || businesses[0]?.business_id;
  const subscription = useSubscription(businessId);
  const [extra, setExtra] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [interval, setInterval] = useState("month");
  const gate = useRef(false);
  const [busy, setBusy] = useState(false);
  const [billingError, setBillingError] = useState(false);
  // Run the requested billing action and handle its result before allowing another billing interaction.
  async function billingAction(action, portal = false) {
    if (gate.current) return;
    gate.current = true; setBusy(true); setBillingError(false);
    try {
      const result = await action();
      if (result.url) window.location.assign(billingRedirect(result.url, portal));
      else {
        if (['NO_PENDING_ATTEMPT', 'EXPIRED', 'COMPLETE'].includes(result.status)) {
          for (const plan of ['PRO', 'BUSINESS']) for (const period of ['month', 'year']) {
            window.sessionStorage.removeItem(`lankapex-checkout:${businessId}:${plan}:${period}`);
          }
        }
        subscription.retry();
      }
    } catch { setBillingError(true); }
    finally { gate.current = false; setBusy(false); }
  }
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(() => {
    if (!businessId) return;
    const controller = new AbortController();
    Promise.all([getSubscriptionPlans(controller.signal), getSubscriptionHistory(businessId, controller.signal)])
      .then(([plans, history]) => { if (!controller.signal.aborted) setExtra({ businessId, attempt, plans, history }); })
      .catch(() => { if (!controller.signal.aborted) setExtra({ businessId, attempt, error: true }); });
    return () => controller.abort();
  }, [businessId, attempt]);
  const current = extra && extra.businessId === businessId && extra.attempt === attempt ? extra : null;
  return <SubscriptionBillingView businesses={businesses} businessId={businessId} onBusiness={id => setParams(id ? { business_id: id } : {})}
    data={subscription.data} plans={current?.plans?.plans} history={current?.history} interval={interval} onInterval={setInterval}
    loading={subscription.loading || Boolean(businessId && !current)} error={subscription.error || current?.error}
    busy={busy} billingError={billingError} checkoutReturn={params.get('checkout')}
    onCheckout={plan => billingAction(() => createCheckout(businessId, plan, interval,
      checkoutRequestKey(window.sessionStorage, businessId, plan, interval, () => crypto.randomUUID())))}
    onPortal={() => billingAction(() => createPortal(businessId), true)}
    onReconcile={() => billingAction(() => reconcileCheckout(businessId))}
    onRetry={() => { subscription.retry(); setAttempt(value => value + 1); }} />;
}
