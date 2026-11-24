// Purpose: Render the customer dashboard screen and connect its user interactions to shared application state and services.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { Link } from "react-router-dom";
import CustomerCreditOverview from "../../components/customer/CustomerCreditOverview";
import CustomerRecentOrders from "../../components/customer/CustomerRecentOrders";
import { useEffect, useState, useSyncExternalStore } from "react";
import { RefreshCw, LoaderCircle, CalendarClock } from "lucide-react";
import { useAuth } from "../../context/useAuth";
import { getCustomerSummary, getCustomerShops, getCustomerCreditAccounts, getCustomerTransactions } from "../../services/customerDashboardService";
import { createCustomerDashboardReader, formatCustomerMoney, formatRecordedTime } from "../../utils/customerDashboard";

const button = "inline-flex items-center gap-2 rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm font-semibold text-[#36517B] focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50";
const card = "min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-6";
const typeLabel = { credit_sale: "Credit sale", repayment: "Repayment record", reversal: "Reversal" };
// Render the loading interface and connect its controls to the state and callbacks defined here.
function Loading({ children }) { return <p role="status" className="flex items-center gap-2 py-6 text-sm text-[#64748B]"><LoaderCircle size={18} className="animate-spin motion-reduce:animate-none" aria-hidden="true" />{children}</p>; }
// Render the section interface and connect its controls to the state and callbacks defined here.
function Section({ id, title, section, retry, children }) {
  const { tr } = useAppTranslation();
  return <section id={id} aria-labelledby={id + "-heading"} className={card + " scroll-mt-6"}>
    <h2 id={id + "-heading"} className="text-xl font-bold">{tr(title)}</h2>
    {section.loading ? <Loading>{tr("Loading")}{" "}{title.toLowerCase()}...</Loading> : section.error ? <div role="alert" className="my-5 space-y-3 border-l-4 border-[#DC4545] pl-3 text-sm text-[#10243E]"><p>{tr(section.error)}</p><button type="button" className={button} onClick={retry}>{tr("Retry")}{" "}{title.toLowerCase()}</button></div> : section.data ? children : <p className="py-5 text-sm text-[#64748B]">{tr("Data unavailable.")}</p>}
  </section>;
}
// Render the preview note interface and connect its controls to the state and callbacks defined here.
function PreviewNote({ data }) {
  const { tr } = useAppTranslation(); return <p className="mt-4 text-xs text-[#64748B]">{tr("Showing {{shown}} of {{total}} records.", { shown: data.items.length, total: data.total })}</p>; }
// Render the customer dashboard view interface and connect its controls to the state and callbacks defined here.
export function CustomerDashboardView({ state, actions }) {
  const { tr, statusLabel } = useAppTranslation();
  const summary = state.summary.data;

  const busy = ["summary", "shops", "accounts", "transactions"].some(key => state[key].loading);
  return <div className="space-y-7 pb-6">
    <div className="flex justify-end"><button type="button" className={button} disabled={busy} onClick={actions.start}><RefreshCw size={17} aria-hidden="true" />{tr("Refresh dashboard")}</button></div>
    {state.authError ? <p role="alert" className="rounded-xl border border-[#DC4545] bg-white p-5 text-sm text-[#10243E]">{tr(state.authError)}</p> : <>
      <section aria-label={tr("Customer overview")}>
        {state.summary.loading && <Loading>{tr("Loading your account summary...")}</Loading>}
        {state.summary.error && <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 border-l-4 border-[#DC4545] pl-3 text-sm text-[#10243E]"><p>{tr(state.summary.error)}</p><button type="button" className={button} onClick={() => actions.load("summary")}>{tr("Retry summary")}</button></div>}
        <CustomerCreditOverview summary={summary} loading={state.summary.loading}/>
      </section>
      <Section id="my-credit" title={tr("My Credit Accounts")} section={state.accounts} retry={() => actions.load("accounts")}>
        {state.accounts.data && (state.accounts.data.items.length ? <><div className="customer-table-wrap"><table><thead><tr>{['Shop','Outstanding','Next Due Date','Status','Action'].map(label=><th key={label}>{tr(label)}</th>)}</tr></thead><tbody>{state.accounts.data.items.map(account=><tr key={account.credit_account_id}><td><p className="font-semibold">{account.business_name}</p><p className="mt-1 text-xs text-[#64748B]">{tr("Account #")}{account.credit_account_id}</p></td><td className="font-bold">{formatCustomerMoney(account.outstanding_balance)}</td><td className="text-[#64748B]">{tr("Unavailable")}</td><td><span className="rounded-full bg-[#E7F9F6] px-3 py-1 text-xs">{statusLabel(account.account_status)}</span></td><td><Link to={'/customer/credit/'+account.credit_account_id} className={button}>{tr("View Ledger")}</Link><p className="mt-1 text-xs text-[#64748B]">{tr("Credit limit:")}{" "}{formatCustomerMoney(account.credit_limit)}</p></td></tr>)}</tbody></table></div><PreviewNote data={state.accounts.data} /></> : <p className="py-6 text-sm text-[#64748B]">{tr("No credit accounts are linked to your account yet.")}</p>)}
      </Section>
      <CustomerRecentOrders />
      <Section id="transactions" title={tr("Recent Transactions")} section={state.transactions} retry={() => actions.load("transactions")}>
        {state.transactions.data && (state.transactions.data.items.length ? <><p className="mt-2 text-xs text-[#64748B]">{tr("Newest records first. A repayment record does not independently verify bank or card settlement.")}</p><ul className="mt-5 divide-y divide-[#E1EAF4]">{state.transactions.data.items.map(row => <li key={row.entry_id} className="grid min-w-0 gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{tr(typeLabel[row.entry_type])}</h3>{row.status !== "recorded" && <span className="rounded-full bg-[#F5B544]/15 px-2 py-1 text-xs capitalize">{statusLabel(row.status)}</span>}</div><p className="mt-1 break-words text-sm">{row.business_name}</p><p className="mt-1 break-all text-xs text-[#64748B]">{row.reference}</p><time dateTime={row.recorded_at} className="mt-1 block text-xs text-[#64748B]" title={tr("Recorded time")}>{formatRecordedTime(row.recorded_at)}</time></div><div className="min-w-0 sm:max-w-64 sm:text-right"><p className="break-words font-bold [overflow-wrap:anywhere]">{formatCustomerMoney(row.amount)}</p>{row.entry_type === "reversal" && <p className="mt-1 break-words text-xs text-[#64748B] [overflow-wrap:anywhere]">{tr("Balance adjustment:")}{" "}{formatCustomerMoney(row.balance_delta)}</p>}</div></li>)}</ul><PreviewNote data={state.transactions.data} /></> : <p className="py-6 text-sm text-[#64748B]">{tr("No transactions to display yet.")}</p>)}
      </Section>
      <section className="flex flex-wrap items-center gap-4 rounded-xl border border-[#F5B544]/40 bg-[#FFFBF1] p-5"><CalendarClock size={30} className="text-[#C78513]" aria-hidden="true"/><div className="min-w-0 flex-1"><h3 className="font-bold">{tr("Next Payment")}</h3><p className="mt-1 text-sm text-[#52698A]">{tr("Next payment amount and deadline are unavailable.")}</p></div><Link to="/customer/transactions?entry_type=repayment" className={button}>{tr("View repayment records")}</Link></section>
    </>}
  </div>;
}
// Render the customer dashboard session interface and connect its controls to the state and callbacks defined here.
function CustomerDashboardSession() {
  const [reader] = useState(() => createCustomerDashboardReader({ summary: getCustomerSummary, shops: getCustomerShops, accounts: getCustomerCreditAccounts, transactions: getCustomerTransactions }));
  const state = useSyncExternalStore(reader.subscribe, reader.getSnapshot, reader.getSnapshot);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(() => { reader.start(); return () => reader.dispose(); }, [reader]);
  return <CustomerDashboardView state={state} actions={reader} />;
}
// Render the customer dashboard interface and connect its controls to the state and callbacks defined here.
export default function CustomerDashboard() {
  const { user, token, isAuthenticated } = useAuth();
  if (!isAuthenticated || user?.platform_role !== "customer") return null;
  return <CustomerDashboardSession key={user.user_id + ":" + token} />;
}
