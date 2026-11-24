// Purpose: Render the shop owner repayments screen and connect its user interactions to shared application state and services.
import Select from "../../components/ui/Select";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useEffect, useState, useSyncExternalStore } from "react";
import { Link, useLocation } from "react-router-dom";
import { CreditCard, RefreshCw, Wallet, Coins, Plus } from "lucide-react";
import { useAuth } from "../../context/useAuth";
import { getShopOwnerBusinessContext } from "../../services/shopOwnerBusinessService";
import { getShopOwnerCustomers, getShopOwnerCustomerDetails } from "../../services/shopOwnerCustomerService";
import { createShopOwnerRepayment } from "../../services/shopOwnerRepaymentService";
import { formatCreditMoney, sessionRepaymentStore, repaymentValidation, PAYMENT_METHODS } from "../../utils/repayment";
import { createRepaymentWorkflow } from "./repaymentWorkflow";

import FinancialDocuments, { ReceiptActions } from "./FinancialDocuments";

const fieldClass = "mt-1.5 w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2.5 text-sm text-[#0D1D47] outline-none focus:border-[#0BAAB4] focus:ring-2 focus:ring-[#0BAAB4]/15";
const api = { businesses: getShopOwnerBusinessContext, customers: getShopOwnerCustomers,
  details: getShopOwnerCustomerDetails, record: createShopOwnerRepayment };

// Render the money card interface and connect its controls to the state and callbacks defined here.
function MoneyCard({ icon: Icon, label, value, palette }) {
  const { tr } = useAppTranslation();
  return <div className="flex items-center gap-4 rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm">
    <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${palette}`}><Icon size={23} /></div>
    <div><p className="text-xs font-semibold text-[#587098]">{tr(label)}</p><p className="mt-1 text-xl font-extrabold text-[#0D1D47]">{value == null ? tr("Not set") : formatCreditMoney(value)}</p></div>
  </div>;
}

// Format date label for display so screens use a consistent representation.
function dateLabel(value) {
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime()) ? date.toLocaleString("en-LK") : "?";
}

// Render the repayments view interface and connect its controls to the state and callbacks defined here.
export function RepaymentsView({ state, actions }) {
  const { tr } = useAppTranslation();
  const business = state.businesses.find(b => String(b.business_id) === String(state.businessId));
  const approved = business?.approval_status === "approved";
  const details = state.details;
  const account = details?.credit_account;
  const busy = state.saving || state.contextLoading;
  const blocked = busy || !approved || !account || state.customersLoading || state.detailsLoading ||
    !!state.detailsError || !!state.customersError || !!state.contextError || !!state.storageError ||
    !!repaymentValidation(state) ||
    (!state.uncertain && !["active", "suspended"].includes(account.account_status));
  const payments = details?.transactions?.filter(entry => entry.entry_type === "repayment") || [];
  const success = state.success;
  return <div className="space-y-5 pb-8">
    <div><h2 className="text-[26px] font-extrabold text-[#0D1D47]">{tr("Repayments")}</h2><p className="text-sm text-[#587098]">{tr("Record customer repayments and review their credit accounts.")}</p></div>
    <div className="flex flex-wrap items-center gap-3">
      <label htmlFor="repayment-business" className="text-sm font-semibold text-[#0D1D47]">{tr("Business")}</label>
      <Select id="repayment-business" className="max-w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm" value={state.businessId} disabled={busy || !state.businesses.length} onChange={event => actions.selectBusiness(event.target.value)}>
        {!state.businesses.length && <option value="">{tr("No linked businesses")}</option>}
        {state.businesses.map(item => <option key={item.business_id} value={item.business_id}>{item.business_name} ({tr(item.approval_status)})</option>)}
      </Select>
      <button type="button" disabled={state.saving || state.contextLoading || state.customersLoading || state.detailsLoading} onClick={() => state.contextError ? actions.loadBusinesses() : actions.refresh()} className="rounded-lg border border-[#DAE5F3] bg-white p-2 text-[#36517B] disabled:opacity-50" aria-label={tr("Refresh repayment data")} title={tr("Refresh repayment data")}><RefreshCw size={18} /></button>
    </div>
    {state.contextLoading && <p role="status" className="text-sm text-[#587098]">{tr("Loading business information...")}</p>}
    {state.contextError && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{tr(state.contextError)}</p>}
    {!state.contextLoading && !state.contextError && !business && <p className="rounded-xl bg-white p-5 text-sm text-[#587098]">{tr("No business is linked to your account.")} <Link to="/shop-owner/business/register" className="font-semibold text-[#1265D6] underline">{tr("Register a business")}</Link> {tr("first.")}</p>}
    {business && !approved && <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{tr("Business approval is required before recording repayments. Current status:")} <strong>{tr(business.approval_status)}</strong>.</p>}
    {state.uncertain && <div role="alert" className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
      <p>{tr("A repayment may already have been recorded in this browser tab. Refresh and review the customer ledger before starting another repayment. To confirm the original result, re-enter the same business, customer, amount, method, reference and notes, then retry the same repayment.")}</p>
      <p>{tr("Retrying the identical payment confirms its result without recording it twice.")}</p>
    </div>}
    {!state.error && state.amount && repaymentValidation(state) && <p role="alert" className="text-sm text-red-700">{tr(repaymentValidation(state))}</p>}
    {state.error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{tr(state.error)}</p>}
    {success && <section role="status" aria-label={tr("Confirmed repayment")} className="space-y-2 rounded-xl border border-[#BDE9D6] bg-[#E5F8EF] p-4 text-sm text-[#118456]">
      <p className="font-bold">{success.replayed ? tr("Existing repayment confirmed. No duplicate entry was created.") : tr("Repayment recorded successfully.")}</p>
      <p>{tr("Reference:")} <strong>{success.reference}</strong> {tr("| Transaction ID:")} {success.entry_id}</p>
      <p>{tr("Repayment:")} {formatCreditMoney(success.amount)} {tr("| Outstanding:")} {formatCreditMoney(success.outstanding_balance)} {tr("| Available credit:")} {formatCreditMoney(success.available_credit)}</p>
      <ReceiptActions key={`${state.businessId}:${success.entry_id}`} businessId={state.businessId} entryId={success.entry_id} />
      <p>{tr("Method:")} {tr(PAYMENT_METHODS.find(([value]) => value === success.payment_method)?.[1])} {tr("| Recorded:")} {dateLabel(success.recorded_at)}</p>
    </section>}
    {approved && !state.contextError && <>
      <section className="owner-transaction rounded-xl border border-[#E1EAF4] bg-white p-5 space-y-4"><h3 className="text-xl font-bold">{tr("Record Repayment")}</h3>
      <section className="rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5">
        <label htmlFor="repayment-customer" className="text-sm font-semibold text-[#0D1D47]">{tr("Customer")}</label>
        <Select id="repayment-customer" value={state.customerId} disabled={busy || state.customersLoading || !!state.customersError || !state.customers.length} onChange={event => actions.selectCustomer(event.target.value)} className={fieldClass}>
          <option value="">{tr("Select a customer")}</option>
          {state.customers.map(customer => <option key={customer.customer_id} value={customer.customer_id}>{customer.customer_name}{customer.phone ? ` | ${customer.phone}` : ""}</option>)}
        </Select>
        {state.customersLoading && <p role="status" className="mt-2 text-sm text-[#587098]">{tr("Loading customers...")}</p>}
        {state.customersError && <p role="alert" className="mt-2 text-sm text-red-700">{tr(state.customersError)}</p>}
        {!state.customersLoading && !state.customersError && !state.customers.length && <p className="mt-2 text-sm text-[#587098]">{tr("No customers in this business.")} <Link to="/shop-owner/customers" className="text-[#1265D6] underline">{tr("Add a customer")}</Link> {tr("first.")}</p>}
      </section>
      {state.detailsLoading && <p role="status" className="text-sm text-[#587098]">{tr("Loading customer credit account...")}</p>}
      {state.detailsError && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{tr(state.detailsError)}{success ? tr(" The repayment is confirmed; refreshed ledger data is temporarily unavailable.") : ""}</p>}
      {details && <>
        {account && details.outstanding_balance === "0.00" && <p className="rounded-lg bg-[#E5F8EF] p-4 text-sm text-[#118456]">{tr("This customer has no outstanding debt.")}</p>}
        <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-lg font-bold text-[#0D1D47]">{details.customer.customer_name}</h3><span className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${account?.account_status === "active" ? "bg-[#E5F8EF] text-[#118456]" : "bg-[#FFF1DD] text-[#9B6817]"}`}>{account?.account_status ? tr(account.account_status) : tr("No credit account")}</span></div>
        <div className="grid gap-3 md:grid-cols-3">
          <MoneyCard icon={Wallet} label={tr("Outstanding Balance")} value={details.outstanding_balance} palette="bg-[#EAF6FF] text-[#1265D6]" />
          <MoneyCard icon={CreditCard} label={tr("Credit Limit")} value={account?.credit_limit} palette="bg-[#EAF2F9] text-[#36517B]" />
          <MoneyCard icon={Coins} label={tr("Available Credit")} value={details.available_credit} palette="bg-[#E7F9F6] text-[#0BAAB4]" />
        </div>
        {!account && <p className="rounded-lg bg-amber-50 p-4 text-sm text-amber-800">{tr("This customer has no credit account.")} <Link to="/shop-owner/customers" className="font-semibold underline">{tr("Manage customer credit accounts")}</Link> {tr("before recording a repayment.")}</p>}
        {account && !["active", "suspended"].includes(account.account_status) && <p className="rounded-lg bg-amber-50 p-4 text-sm text-amber-800">{tr("This account is")} {tr(account.account_status)}{tr(". New repayments require an active or suspended account.")}{state.uncertain ? tr(" You may still retry the unchanged original request to confirm its result.") : ""}</p>}
      </>}
      <section className="rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5">
        <h3 className="mb-4 text-lg font-bold text-[#0D1D47]">{tr("Record Repayment")}</h3>
        <form noValidate onSubmit={event => { event.preventDefault(); void actions.submit(); }} className="space-y-4">
          <fieldset disabled={state.saving || !approved || !account || state.detailsLoading} className="space-y-4 disabled:opacity-60">
            <label className="block text-sm font-semibold text-[#36517B]" htmlFor="repayment-amount">{tr("Repayment amount (LKR)")}<input id="repayment-amount" name="amount" type="text" inputMode="decimal" autoComplete="off" required maxLength={20} value={state.amount} onChange={event => actions.edit("amount", event.target.value)} placeholder="0.00" aria-describedby="repayment-amount-help" className={fieldClass} /></label>
            <p id="repayment-amount-help" className="text-xs text-[#587098]">{tr("Enter a positive amount with at most two decimal places. The server checks the outstanding balance before recording.")}</p>
            <button type="button" onClick={() => actions.fullPayment()} className="text-sm font-semibold text-[#1265D6] underline">{tr("Full Payment")}</button>
            <label className="block text-sm font-semibold text-[#36517B]" htmlFor="repayment-method">{tr("Payment method")}<Select id="repayment-method" value={state.payment_method} onChange={event => actions.edit("payment_method", event.target.value)} className={fieldClass}>{PAYMENT_METHODS.map(([value, label]) => <option key={value} value={value}>{tr(label)}</option>)}</Select></label>
            <label className="block text-sm font-semibold text-[#36517B]" htmlFor="repayment-reference">{tr("Reference (optional)")}<input id="repayment-reference" value={state.receipt_number} maxLength={60} onChange={event => actions.edit("receipt_number", event.target.value)} className={fieldClass} /><span className="text-xs font-normal">{tr("Leave blank to assign a receipt reference. CS- and RP- prefixes are reserved.")}</span></label>
            <label className="block text-sm font-semibold text-[#36517B]" htmlFor="repayment-notes">{tr("Notes (optional)")}<textarea id="repayment-notes" name="notes" rows={3} maxLength={2000} value={state.notes} onChange={event => actions.edit("notes", event.target.value)} className={fieldClass} /></label>
            <p className="text-xs text-[#587098]">{tr("Payments are recorded manually; bank transfers and cards are not electronically verified.")}</p>
          </fieldset>
          <div className="flex flex-wrap justify-end gap-3">
            <button type="button" disabled={state.saving} onClick={() => actions.newRepayment()} className="rounded-lg border border-[#DAE5F3] px-4 py-2.5 text-sm font-semibold text-[#36517B] disabled:opacity-50">{state.uncertain || state.storageError ? tr("After Checking Ledger, Start New Repayment") : tr("Clear Form")}</button>
            <button type="submit" disabled={blocked} className="inline-flex items-center gap-2 rounded-lg bg-[#0BAAB4] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#0997A0] disabled:cursor-not-allowed disabled:opacity-60"><Plus size={17} />{state.saving ? tr("Recording...") : state.uncertain ? tr("Retry Same Repayment") : tr("Record Repayment")}</button>
          </div>
        </form>
      </section>
      </section>
      {details && <section className="overflow-hidden rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5">
        <h3 className="text-lg font-bold text-[#0D1D47]">{tr("Repayment History")}</h3><p className="mb-4 text-xs text-[#587098]">{tr("Effective repayments from this customer's current ledger. Reversed repayments are excluded.")}</p>
        <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-[#EAF2F9] text-[#0D1D47]"><tr>{["Date", "Reference", "Repayment Amount", "Running Balance", "Method", "Receipt"].map(label => <th key={label} className="px-3 py-3">{tr(label)}</th>)}</tr></thead><tbody>
          {payments.map(entry => <tr key={entry.entry_id} className="border-b border-[#E8EEF5] text-[#36517B]"><td className="px-3 py-3">{dateLabel(entry.recorded_at)}</td><td className="px-3 py-3">{entry.reference}</td><td className="px-3 py-3">{formatCreditMoney(entry.credit)}</td><td className="px-3 py-3">{formatCreditMoney(entry.running_balance)}</td><td className="px-3 py-3">{tr(PAYMENT_METHODS.find(([value]) => value === entry.payment_method)?.[1] || entry.payment_method || "Not recorded")}</td><td className="px-3 py-3"><ReceiptActions businessId={state.businessId} entryId={entry.entry_id} /></td></tr>)}
          {!payments.length && <tr><td colSpan={6} className="px-3 py-8 text-center text-[#587098]">{state.detailsLoading ? tr("Refreshing customer repayments...") : tr("No effective repayments for this customer.")}</td></tr>}
        </tbody></table></div>
      </section>}
      <FinancialDocuments key={state.businessId} businessId={state.businessId} customerId={state.customerId} refreshToken={details} onSelectCustomer={actions.selectCustomer} />
    </>}
  </div>;
}

// Render the repayments page interface and connect its controls to the state and callbacks defined here.
function RepaymentsPage({ userId, initialBusinessId, initialCustomerId }) {
  const [workflow] = useState(() => createRepaymentWorkflow({ api, store: sessionRepaymentStore(userId), initialBusinessId, initialCustomerId }));
  const state = useSyncExternalStore(workflow.subscribe, workflow.getSnapshot, workflow.getSnapshot);
  // Attach browser listeners for this mounted resource and remove them during effect cleanup.
  useEffect(() => {
    void workflow.loadBusinesses();
    // Explain that the previous write still needs confirmation before a new operation can start.
    const warnPending = event => {
      const current = workflow.getSnapshot();
      if (current.saving || current.uncertain) { event.preventDefault(); event.returnValue = ""; }
    };
    window.addEventListener("beforeunload", warnPending);
    return () => { workflow.dispose(); window.removeEventListener("beforeunload", warnPending); };
  }, [workflow]);
  return <RepaymentsView state={state} actions={workflow} />;
}

// Render the shop owner repayments interface and connect its controls to the state and callbacks defined here.
export default function ShopOwnerRepayments() {
  const { user } = useAuth();
  const location = useLocation();
  return <RepaymentsPage key={user.user_id} userId={user.user_id} initialBusinessId={location.state?.businessId} initialCustomerId={location.state?.customerId} />;
}
