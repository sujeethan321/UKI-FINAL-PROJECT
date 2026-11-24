// Purpose: Render the financial documents screen and connect its user interactions to shared application state and services.
import PlanFeatureNotice from '../../components/shopOwner/PlanFeatureNotice';
import usePlanAccess from '../../hooks/usePlanAccess';
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import BrandLogo from "../../components/BrandLogo";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { getRepaymentReceipt, getCustomerStatement, getOutstandingPayments } from "../../services/shopOwnerFinancialDocumentService";
import { createFinancialReader, validateReceipt, validateStatement, validateOutstanding, formatDocumentMoney } from "../../utils/financialDocuments";
import { PAYMENT_METHODS } from "../../utils/repayment";
import "./financialDocuments.css";

const button = "rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm font-semibold text-[#36517B] disabled:opacity-50";
const field = "rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm text-[#0D1D47]";
// Format method label for display so screens use a consistent representation.
const methodLabel = value => PAYMENT_METHODS.find(([method]) => method === value)?.[1] || value || "Not recorded";
// Stored financial timestamps have no offset; show their recorded wall time,
// avoiding the browser silently shifting historical transactions across dates.
const recordedDate = value => value ? value.replace("T", " ") : "Not recorded";
// Derive the current calendar-date value used by the form.
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

// Share reader state and lifecycle behavior between React consumers.
function useReader(api, validate) {
  const [reader] = useState(() => createFinancialReader(api, validate));
  const state = useSyncExternalStore(reader.subscribe, reader.getSnapshot, reader.getSnapshot);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(() => () => reader.dispose(), [reader]);
  return [reader, state];
}

// Render the document modal interface and connect its controls to the state and callbacks defined here.
function DocumentModal({ title, onClose, printable, children }) {
  const { tr } = useAppTranslation();
  const modal = useRef(null);
  // Attach browser listeners for this mounted resource and remove them during effect cleanup.
  useEffect(() => {
    const previous = document.activeElement;
    // Close the open interface and reset the state defined by this handler.
    const close = event => {
      const overlays = document.querySelectorAll(".lpx-document-overlay");
      if (overlays[overlays.length - 1] !== modal.current?.parentElement) return;
      if (event.key === "Escape") { event.stopImmediatePropagation(); onClose(); }
      if (event.key === "Tab") {
        const controls = modal.current.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled)');
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("keydown", close); previous?.focus?.(); };
  }, [onClose]);
  return createPortal(<div className="lpx-document-overlay fixed inset-0 z-[80] overflow-y-auto bg-[#10243E]/60 p-4 sm:p-8">
    <section ref={modal} role="dialog" aria-modal="true" aria-label={tr(title)} className="lpx-document-print mx-auto w-full max-w-4xl rounded-xl border border-[#E1EAF4] bg-white p-5 text-[#0D1D47] shadow-xl sm:p-8">
      <div className="lpx-no-print mb-5 flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-bold">{tr(title)}</h2><div className="flex gap-2"><button type="button" className={button} disabled={!printable} onClick={() => window.print()}>{tr("Print / Save PDF")}</button><button type="button" autoFocus className={button} onClick={onClose}>{tr("Close")}</button></div></div>
      {children}
    </section>
  </div>, document.body);
}

// Render the document identity interface and connect its controls to the state and callbacks defined here.
function DocumentIdentity({ business, customer, title }) {
  const { tr } = useAppTranslation();
  return <header className="mb-6 space-y-1 border-b border-[#DAE5F3] pb-5"><BrandLogo /><h2 className="pt-3 text-xl font-bold">{tr(title)}</h2><p className="font-semibold">{business.business_name}</p>{business.address && <p>{business.address}</p>}{business.phone && <p>{tr("Shop phone:")} {business.phone}</p>}<p className="pt-3">{tr("Customer:")} <strong>{customer.customer_name}</strong> {tr("(ID")} {customer.customer_id})</p>{customer.phone && <p>{tr("Customer phone:")} {customer.phone}</p>}</header>;
}

// Render the receipt content interface and connect its controls to the state and callbacks defined here.
export function ReceiptContent({ receipt }) {
  const { tr } = useAppTranslation();
  return <article>
    <DocumentIdentity business={receipt.business} customer={receipt.customer} title={tr("Repayment Receipt")} />
    {receipt.status === "reversed" && <p role="alert" className="mb-5 rounded-lg border-2 border-red-600 p-4 text-lg font-extrabold text-red-700">{tr("REVERSED / VOID — This repayment no longer settles debt.")}</p>}
    <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm"><dt>{tr("Status")}</dt><dd className="font-bold capitalize">{tr(receipt.status)}</dd><dt>{tr("Receipt / reference")}</dt><dd className="break-all font-semibold">{receipt.reference}</dd><dt>{tr("Stable receipt ID")}</dt><dd>{receipt.receipt_identifier}</dd><dt>{tr("Transaction ID")}</dt><dd>{receipt.entry_id}</dd><dt>{tr("Amount recorded")}</dt><dd className="text-xl font-bold">{formatDocumentMoney(receipt.amount)}</dd><dt>{tr("Method")}</dt><dd>{tr(methodLabel(receipt.payment_method))}</dd><dt>{tr("Recorded")}</dt><dd>{recordedDate(receipt.recorded_at)}</dd></dl>
    {receipt.status === "reversed" && <p className="mt-4 text-sm text-red-700">{tr("Reversal transaction")} {receipt.reversal_entry_id}{tr(", recorded")} {recordedDate(receipt.reversed_at)}.</p>}
    {receipt.notes && <p className="mt-5 whitespace-pre-wrap break-words text-sm">{tr("Notes:")} {receipt.notes}</p>}
    <p className="mt-6 border-t border-[#DAE5F3] pt-4 text-xs text-[#587098]">{tr("Manual payment record. This receipt does not verify a bank transfer or card settlement. Dates use the shop ledger's recorded clock.")}</p>
  </article>;
}

// Render the receipt actions interface and connect its controls to the state and callbacks defined here.
export function ReceiptActions({ businessId, entryId }) {
  const { tr } = useAppTranslation();
  const [reader, state] = useReader(getRepaymentReceipt, validateReceipt);
  const [open, setOpen] = useState(false);
  const [printRequested, setPrintRequested] = useState(false);
  const close = useCallback(() => { setOpen(false); setPrintRequested(false); reader.clear(); }, [reader]);
  // Open the selected record or document in the current workflow.
  const show = print => { setOpen(true); setPrintRequested(print); void reader.load(businessId, entryId); };
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => {
    if (!open || !state.data || !printRequested) return;
    const handle = requestAnimationFrame(() => { setPrintRequested(false); window.print(); });
    return () => cancelAnimationFrame(handle);
  }, [open, state.data, printRequested]);
  return <>
    <span className="inline-flex flex-wrap gap-2"><button type="button" className={button} disabled={state.loading} onClick={() => show(false)}>{tr("View Receipt")}</button><button type="button" className={button} disabled={state.loading} onClick={() => show(true)}>{tr("Print Receipt")}</button></span>
    {open && <DocumentModal title={tr("Repayment Receipt")} onClose={close} printable={!!state.data}>
      {state.loading && <p role="status">{tr("Loading recorded receipt...")}</p>}
      {state.error && <div role="alert" className="text-sm text-red-700">{tr(state.error)}<button type="button" className={`${button} ml-3`} onClick={() => show(false)}>{tr("Retry")}</button></div>}
      {state.data && <ReceiptContent receipt={state.data} />}
    </DocumentModal>}
  </>;
}

// Render the statement content interface and connect its controls to the state and callbacks defined here.
export function StatementContent({ statement }) {
  const { tr } = useAppTranslation();
  return <article>
    <DocumentIdentity business={statement.business} customer={statement.customer} title={tr("Customer Credit Statement")} />
    <p className="mb-4 text-sm">{tr("Period:")} {statement.start_date} {tr("to")} {statement.end_date} {tr("(inclusive)")}</p>
    <dl className="mb-5 grid gap-2 text-sm sm:grid-cols-2">{[["Opening balance", statement.opening_balance], ["Credit sales", statement.total_credit_sales], ["Repayments", statement.total_repayments], ["Reversal impact", statement.reversal_impact], ["Closing balance", statement.closing_balance], ["Outstanding at period end", statement.outstanding_balance]].map(([label, value]) => <div key={label} className="flex justify-between gap-4"><dt>{tr(label)}</dt><dd className="font-semibold">{formatDocumentMoney(value)}</dd></div>)}</dl>
    <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-[#EAF2F9]"><tr>{["Date", "Transaction / status", "Reference", "Debit", "Credit", "Balance", "Receipt"].map(label => <th key={label} className={`${label === "Receipt" ? "lpx-no-print " : ""}px-2 py-3`}>{tr(label)}</th>)}</tr></thead><tbody>
      {statement.transactions.map(row => <tr key={row.entry_id} className="border-b border-[#E8EEF5]"><td className="px-2 py-3">{recordedDate(row.recorded_at)}</td><td className="px-2 py-3">{tr(row.entry_type)} / <strong>{tr(row.status)}</strong>{row.reverses_entry_id && <span> {tr("(reverses #")}{row.reverses_entry_id})</span>}</td><td className="px-2 py-3">{row.reference}</td><td className="px-2 py-3">{formatDocumentMoney(row.debit)}</td><td className="px-2 py-3">{formatDocumentMoney(row.credit)}</td><td className="px-2 py-3">{formatDocumentMoney(row.running_balance)}</td><td className="lpx-no-print px-2 py-3">{row.entry_type === "repayment" && <ReceiptActions businessId={statement.business.business_id} entryId={row.entry_id} />}</td></tr>)}
      {!statement.transactions.length && <tr><td colSpan={7} className="p-5 text-center">{tr("No activity in this period.")}</td></tr>}
    </tbody></table></div>
    <p className="mt-5 text-xs text-[#587098]">{tr(statement.reversal_policy)}</p><p className="mt-2 text-xs text-[#587098]">{tr(statement.time_basis)}</p><p className="mt-2 text-xs text-[#587098]">{tr(statement.historical_limitations)}</p>
  </article>;
}

// Render the outstanding view interface and connect its controls to the state and callbacks defined here.
export function OutstandingView({ state, onSelectCustomer }) {
  const { tr } = useAppTranslation();
  if (state.loading) return <p role="status" className="text-sm text-[#587098]">{tr("Loading outstanding payments...")}</p>;
  if (state.error) return <p role="alert" className="text-sm text-red-700">{tr(state.error)}</p>;
  const data = state.data;
  if (!data) return null;
  return <>
    <div className="my-4 grid gap-3 sm:grid-cols-3">{[["Total Outstanding", formatDocumentMoney(data.total_outstanding)], ["Customers with Outstanding", data.customers_with_outstanding], ["Overdue", "Unavailable"]].map(([label, value]) => <div key={label} className="rounded-xl border border-[#E1EAF4] bg-white p-4"><p className="text-xs font-semibold text-[#587098]">{tr(label)}</p><p className="mt-1 text-xl font-extrabold text-[#0D1D47]">{value}</p></div>)}</div>
    <p className="mb-4 text-xs text-[#587098]">{tr(data.overdue_unavailable_reason)} {tr("Totals cover the whole selected business.")}</p>
    <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-sm"><thead className="bg-[#EAF2F9]"><tr>{["Customer", "Account", "Outstanding", "Credit Limit", "Available Credit", "Action"].map(label => <th className="px-3 py-3" key={label}>{tr(label)}</th>)}</tr></thead><tbody>{data.customers.map(row => <tr key={row.customer_id} className="border-b border-[#E8EEF5]"><td className="px-3 py-3">{row.customer_name}{row.phone && <p className="text-xs">{row.phone}</p>}</td><td className="px-3 py-3 capitalize">{tr(row.account_status)}</td><td className="px-3 py-3">{formatDocumentMoney(row.outstanding_balance)}</td><td className="px-3 py-3">{row.credit_limit == null ? tr("Not set") : formatDocumentMoney(row.credit_limit)}</td><td className="px-3 py-3">{row.available_credit == null ? tr("Not set") : formatDocumentMoney(row.available_credit)}</td><td className="px-3 py-3"><button type="button" className={button} onClick={() => onSelectCustomer(String(row.customer_id))}>{tr("Select Customer")}</button></td></tr>)}{!data.customers.length && <tr><td colSpan={6} className="p-6 text-center text-[#587098]">{tr("No customers match these filters.")}</td></tr>}</tbody></table></div>
  </>;
}

// Render the financial documents interface and connect its controls to the state and callbacks defined here.
export default function FinancialDocuments({ businessId, customerId, refreshToken, onSelectCustomer }) {
  const statementAccess=usePlanAccess(businessId,'statement_exports');
  const { tr } = useAppTranslation();
  const [outstandingReader, outstanding] = useReader(getOutstandingPayments, validateOutstanding);
  const [statementReader, statement] = useReader(getCustomerStatement, validateStatement);
  const [search, setSearch] = useState("");
  const [outstandingOnly, setOutstandingOnly] = useState(true);
  const [page, setPage] = useState(1);
  const [start, setStart] = useState(() => `${today().slice(0, 7)}-01`);
  const [end, setEnd] = useState(today);
  const [statementScope, setStatementScope] = useState(null);
  const showStatement = statementScope?.businessId === businessId && statementScope?.customerId === customerId && statementScope?.refreshToken === refreshToken;
  const [revision, setRevision] = useState(0);
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => {
    void outstandingReader.load(businessId, { search, outstanding_only: outstandingOnly, page, page_size: 10 });
  }, [outstandingReader, businessId, search, outstandingOnly, page, revision, refreshToken]);
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => { statementReader.clear(); }, [statementReader, businessId, customerId, refreshToken]);
  const closeStatement = useCallback(() => { setStatementScope(null); statementReader.clear(); }, [statementReader]);
  // Load statement within the financial documents workflow.
  const loadStatement = () => { if(statementAccess.locked)return; setStatementScope({ businessId, customerId, refreshToken }); void statementReader.load(businessId, customerId, { start_date: start, end_date: end }); };
  const invalidRange = !/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end) || start > end;
  return <section className="space-y-4 rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5">
    <h3 className="text-lg font-bold text-[#0D1D47]">{tr("Outstanding Payments & Statements")}</h3>
    <div className="flex flex-wrap items-center gap-3"><label className="text-sm text-[#36517B]">{tr("Search customers")} <input type="search" maxLength={150} value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} className={field} /></label><label className="flex items-center gap-2 text-sm text-[#36517B]"><input type="checkbox" checked={outstandingOnly} onChange={event => { setOutstandingOnly(event.target.checked); setPage(1); }} />{tr("Outstanding only")}</label><button type="button" className={button} onClick={() => setRevision(value => value + 1)}>{tr("Refresh balances")}</button></div>
    <OutstandingView state={outstanding} onSelectCustomer={onSelectCustomer} />
    {outstanding.data && <div className="flex items-center justify-end gap-3 text-sm"><button type="button" className={button} disabled={outstanding.loading || page <= 1} onClick={() => setPage(value => value - 1)}>{tr("Previous")}</button><span>{tr("Page")} {page} · {outstanding.data.filtered_customers} {tr("matching customers")}</span><button type="button" className={button} disabled={outstanding.loading || page * 10 >= outstanding.data.filtered_customers} onClick={() => setPage(value => value + 1)}>{tr("Next")}</button></div>}
    <PlanFeatureNotice businessId={businessId} feature="statement_exports"/>
    <div className="flex flex-wrap items-end gap-3 border-t border-[#E1EAF4] pt-4"><label className="text-sm text-[#36517B]">{tr("Statement from")}<input type="date" value={start} onChange={event => setStart(event.target.value)} className={`${field} ml-2`} /></label><label className="text-sm text-[#36517B]">{tr("To")}<input type="date" value={end} onChange={event => setEnd(event.target.value)} className={`${field} ml-2`} /></label><button type="button" className={button} disabled={statementAccess.locked || !customerId || invalidRange || statement.loading} onClick={loadStatement}>{tr("View Customer Statement")}</button></div>
    {!customerId && <p className="text-xs text-[#587098]">{tr("Select a customer above to view a statement, including reversed repayments and their receipts.")}</p>}{invalidRange && <p role="alert" className="text-sm text-red-700">{tr("Choose a valid start and end date.")}</p>}
    {showStatement && <DocumentModal title={tr("Customer Credit Statement")} onClose={closeStatement} printable={!!statement.data&&!statementAccess.locked}>{statement.loading && <p role="status">{tr("Loading customer statement...")}</p>}{statement.error && <div role="alert" className="text-sm text-red-700">{tr(statement.error)}<button type="button" className={`${button} ml-3`} onClick={loadStatement}>{tr("Retry")}</button></div>}{statement.data && <StatementContent statement={statement.data} />}</DocumentModal>}
  </section>;
}
