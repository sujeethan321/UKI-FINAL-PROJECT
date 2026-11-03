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

function MoneyCard({ icon: Icon, label, value, palette }) {
  return <div className="flex items-center gap-4 rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm">
    <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${palette}`}><Icon size={23} /></div>
    <div><p className="text-xs font-semibold text-[#587098]">{label}</p><p className="mt-1 text-xl font-extrabold text-[#0D1D47]">{value == null ? "Not set" : formatCreditMoney(value)}</p></div>
  </div>;
}

function dateLabel(value) {
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime()) ? date.toLocaleString("en-LK") : "?";
}

export function RepaymentsView({ state, actions }) {
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
    <div><h2 className="text-[26px] font-extrabold text-[#0D1D47]">Repayments</h2><p className="text-sm text-[#587098]">Record customer repayments and review their credit accounts.</p></div>
    <div className="flex flex-wrap items-center gap-3">
      <label htmlFor="repayment-business" className="text-sm font-semibold text-[#0D1D47]">Business</label>
      <select id="repayment-business" className="max-w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm" value={state.businessId} disabled={busy || !state.businesses.length} onChange={event => actions.selectBusiness(event.target.value)}>
        {!state.businesses.length && <option value="">No linked businesses</option>}
        {state.businesses.map(item => <option key={item.business_id} value={item.business_id}>{item.business_name} ({item.approval_status})</option>)}
      </select>
      <button type="button" disabled={state.saving || state.contextLoading || state.customersLoading || state.detailsLoading} onClick={() => state.contextError ? actions.loadBusinesses() : actions.refresh()} className="rounded-lg border border-[#DAE5F3] bg-white p-2 text-[#36517B] disabled:opacity-50" aria-label="Refresh repayment data" title="Refresh repayment data"><RefreshCw size={18} /></button>
    </div>
    {state.contextLoading && <p role="status" className="text-sm text-[#587098]">Loading business information...</p>}
    {state.contextError && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{state.contextError}</p>}
    {!state.contextLoading && !state.contextError && !business && <p className="rounded-xl bg-white p-5 text-sm text-[#587098]">No business is linked to your account. <Link to="/shop-owner/business/register" className="font-semibold text-[#1265D6] underline">Register a business</Link> first.</p>}
    {business && !approved && <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">Business approval is required before recording repayments. Current status: <strong>{business.approval_status}</strong>.</p>}
    {state.uncertain && <div role="alert" className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
      <p>A repayment may already have been recorded in this browser tab. Refresh and review the customer ledger before starting another repayment. To confirm the original result, re-enter the same business, customer, amount, method, reference and notes, then retry the same repayment.</p>
      <p>Retrying the identical payment confirms its result without recording it twice.</p>
    </div>}
    {!state.error && state.amount && repaymentValidation(state) && <p role="alert" className="text-sm text-red-700">{repaymentValidation(state)}</p>}
    {state.error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{state.error}</p>}
    {success && <section role="status" aria-label="Confirmed repayment" className="space-y-2 rounded-xl border border-[#BDE9D6] bg-[#E5F8EF] p-4 text-sm text-[#118456]">
      <p className="font-bold">{success.replayed ? "Existing repayment confirmed. No duplicate entry was created." : "Repayment recorded successfully."}</p>
      <p>Reference: <strong>{success.reference}</strong> | Transaction ID: {success.entry_id}</p>
      <p>Repayment: {formatCreditMoney(success.amount)} | Outstanding: {formatCreditMoney(success.outstanding_balance)} | Available credit: {formatCreditMoney(success.available_credit)}</p>
      <ReceiptActions key={`${state.businessId}:${success.entry_id}`} businessId={state.businessId} entryId={success.entry_id} />
      <p>Method: {PAYMENT_METHODS.find(([value]) => value === success.payment_method)?.[1]} | Recorded: {dateLabel(success.recorded_at)}</p>
    </section>}
    {approved && !state.contextError && <>
      <section className="rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5">
        <label htmlFor="repayment-customer" className="text-sm font-semibold text-[#0D1D47]">Customer</label>
        <select id="repayment-customer" value={state.customerId} disabled={busy || state.customersLoading || !!state.customersError || !state.customers.length} onChange={event => actions.selectCustomer(event.target.value)} className={fieldClass}>
          <option value="">Select a customer</option>
          {state.customers.map(customer => <option key={customer.customer_id} value={customer.customer_id}>{customer.customer_name}{customer.phone ? ` | ${customer.phone}` : ""}</option>)}
        </select>
        {state.customersLoading && <p role="status" className="mt-2 text-sm text-[#587098]">Loading customers...</p>}
        {state.customersError && <p role="alert" className="mt-2 text-sm text-red-700">{state.customersError}</p>}
        {!state.customersLoading && !state.customersError && !state.customers.length && <p className="mt-2 text-sm text-[#587098]">No customers in this business. <Link to="/shop-owner/customers" className="text-[#1265D6] underline">Add a customer</Link> first.</p>}
      </section>
      {state.detailsLoading && <p role="status" className="text-sm text-[#587098]">Loading customer credit account...</p>}
      {state.detailsError && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{state.detailsError}{success ? " The repayment is confirmed; refreshed ledger data is temporarily unavailable." : ""}</p>}
      {details && <>
        {account && details.outstanding_balance === "0.00" && <p className="rounded-lg bg-[#E5F8EF] p-4 text-sm text-[#118456]">This customer has no outstanding debt.</p>}
        <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-lg font-bold text-[#0D1D47]">{details.customer.customer_name}</h3><span className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${account?.account_status === "active" ? "bg-[#E5F8EF] text-[#118456]" : "bg-[#FFF1DD] text-[#9B6817]"}`}>{account?.account_status || "No credit account"}</span></div>
        <div className="grid gap-3 md:grid-cols-3">
          <MoneyCard icon={Wallet} label="Outstanding Balance" value={details.outstanding_balance} palette="bg-[#EAF6FF] text-[#1265D6]" />
          <MoneyCard icon={CreditCard} label="Credit Limit" value={account?.credit_limit} palette="bg-[#EAF2F9] text-[#36517B]" />
          <MoneyCard icon={Coins} label="Available Credit" value={details.available_credit} palette="bg-[#E7F9F6] text-[#0BAAB4]" />
        </div>
        {!account && <p className="rounded-lg bg-amber-50 p-4 text-sm text-amber-800">This customer has no credit account. <Link to="/shop-owner/customers" className="font-semibold underline">Manage customer credit accounts</Link> before recording a repayment.</p>}
        {account && !["active", "suspended"].includes(account.account_status) && <p className="rounded-lg bg-amber-50 p-4 text-sm text-amber-800">This account is {account.account_status}. New repayments require an active or suspended account.{state.uncertain ? " You may still retry the unchanged original request to confirm its result." : ""}</p>}
      </>}
      <section className="rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5">
        <h3 className="mb-4 text-lg font-bold text-[#0D1D47]">Record Repayment</h3>
        <form noValidate onSubmit={event => { event.preventDefault(); void actions.submit(); }} className="space-y-4">
          <fieldset disabled={state.saving || !approved || !account || state.detailsLoading} className="space-y-4 disabled:opacity-60">
            <label className="block text-sm font-semibold text-[#36517B]" htmlFor="repayment-amount">Repayment amount (LKR)<input id="repayment-amount" name="amount" type="text" inputMode="decimal" autoComplete="off" required maxLength={20} value={state.amount} onChange={event => actions.edit("amount", event.target.value)} placeholder="0.00" aria-describedby="repayment-amount-help" className={fieldClass} /></label>
            <p id="repayment-amount-help" className="text-xs text-[#587098]">Enter a positive amount with at most two decimal places. The server checks the outstanding balance before recording.</p>
            <button type="button" onClick={() => actions.fullPayment()} className="text-sm font-semibold text-[#1265D6] underline">Full Payment</button>
            <label className="block text-sm font-semibold text-[#36517B]" htmlFor="repayment-method">Payment method<select id="repayment-method" value={state.payment_method} onChange={event => actions.edit("payment_method", event.target.value)} className={fieldClass}>{PAYMENT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label className="block text-sm font-semibold text-[#36517B]" htmlFor="repayment-reference">Reference (optional)<input id="repayment-reference" value={state.receipt_number} maxLength={60} onChange={event => actions.edit("receipt_number", event.target.value)} className={fieldClass} /><span className="text-xs font-normal">Leave blank to assign a receipt reference. CS- and RP- prefixes are reserved.</span></label>
            <label className="block text-sm font-semibold text-[#36517B]" htmlFor="repayment-notes">Notes (optional)<textarea id="repayment-notes" name="notes" rows={3} maxLength={2000} value={state.notes} onChange={event => actions.edit("notes", event.target.value)} className={fieldClass} /></label>
            <p className="text-xs text-[#587098]">Payments are recorded manually; bank transfers and cards are not electronically verified.</p>
          </fieldset>
          <div className="flex flex-wrap justify-end gap-3">
            <button type="button" disabled={state.saving} onClick={() => actions.newRepayment()} className="rounded-lg border border-[#DAE5F3] px-4 py-2.5 text-sm font-semibold text-[#36517B] disabled:opacity-50">{state.uncertain || state.storageError ? "After Checking Ledger, Start New Repayment" : "Clear Form"}</button>
            <button type="submit" disabled={blocked} className="inline-flex items-center gap-2 rounded-lg bg-[#0BAAB4] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#0997A0] disabled:cursor-not-allowed disabled:opacity-60"><Plus size={17} />{state.saving ? "Recording..." : state.uncertain ? "Retry Same Repayment" : "Record Repayment"}</button>
          </div>
        </form>
      </section>
      {details && <section className="overflow-hidden rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5">
        <h3 className="text-lg font-bold text-[#0D1D47]">Customer Repayments</h3><p className="mb-4 text-xs text-[#587098]">Effective repayments from this customer's current ledger. Reversed repayments are excluded.</p>
        <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-[#EAF2F9] text-[#0D1D47]"><tr>{["Date", "Reference", "Repayment Amount", "Running Balance", "Method", "Receipt"].map(label => <th key={label} className="px-3 py-3">{label}</th>)}</tr></thead><tbody>
          {payments.map(entry => <tr key={entry.entry_id} className="border-b border-[#E8EEF5] text-[#36517B]"><td className="px-3 py-3">{dateLabel(entry.recorded_at)}</td><td className="px-3 py-3">{entry.reference}</td><td className="px-3 py-3">{formatCreditMoney(entry.credit)}</td><td className="px-3 py-3">{formatCreditMoney(entry.running_balance)}</td><td className="px-3 py-3">{PAYMENT_METHODS.find(([value]) => value === entry.payment_method)?.[1] || entry.payment_method || "Not recorded"}</td><td className="px-3 py-3"><ReceiptActions businessId={state.businessId} entryId={entry.entry_id} /></td></tr>)}
          {!payments.length && <tr><td colSpan={6} className="px-3 py-8 text-center text-[#587098]">{state.detailsLoading ? "Refreshing customer repayments..." : "No effective repayments for this customer."}</td></tr>}
        </tbody></table></div>
      </section>}
      <FinancialDocuments key={state.businessId} businessId={state.businessId} customerId={state.customerId} refreshToken={details} onSelectCustomer={actions.selectCustomer} />
    </>}
  </div>;
}

function RepaymentsPage({ userId, initialBusinessId, initialCustomerId }) {
  const [workflow] = useState(() => createRepaymentWorkflow({ api, store: sessionRepaymentStore(userId), initialBusinessId, initialCustomerId }));
  const state = useSyncExternalStore(workflow.subscribe, workflow.getSnapshot, workflow.getSnapshot);
  useEffect(() => {
    void workflow.loadBusinesses();
    const warnPending = event => {
      const current = workflow.getSnapshot();
      if (current.saving || current.uncertain) { event.preventDefault(); event.returnValue = ""; }
    };
    window.addEventListener("beforeunload", warnPending);
    return () => { workflow.dispose(); window.removeEventListener("beforeunload", warnPending); };
  }, [workflow]);
  return <RepaymentsView state={state} actions={workflow} />;
}

export default function ShopOwnerRepayments() {
  const { user } = useAuth();
  const location = useLocation();
  return <RepaymentsPage key={user.user_id} userId={user.user_id} initialBusinessId={location.state?.businessId} initialCustomerId={location.state?.customerId} />;
}
