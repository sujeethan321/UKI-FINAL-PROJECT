import { useEffect, useState, useSyncExternalStore } from "react";
import { Wallet, Store, CreditCard, History, RefreshCw, LoaderCircle } from "lucide-react";
import { useAuth } from "../../context/useAuth";
import { getCustomerSummary, getCustomerShops, getCustomerCreditAccounts, getCustomerTransactions } from "../../services/customerDashboardService";
import { createCustomerDashboardReader, formatCustomerMoney, formatRecordedTime } from "../../utils/customerDashboard";

const button = "inline-flex items-center gap-2 rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm font-semibold text-[#36517B] focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50";
const card = "min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-6";
const typeLabel = { credit_sale: "Credit sale", repayment: "Repayment record", reversal: "Reversal" };
function Loading({ children }) { return <p role="status" className="flex items-center gap-2 py-6 text-sm text-[#64748B]"><LoaderCircle size={18} className="animate-spin motion-reduce:animate-none" aria-hidden="true" />{children}</p>; }
function Section({ id, title, section, retry, children }) {
  return <section id={id} aria-labelledby={id + "-heading"} className={card + " scroll-mt-6"}>
    <h2 id={id + "-heading"} className="text-xl font-bold">{title}</h2>
    {section.loading ? <Loading>Loading {title.toLowerCase()}...</Loading> : section.error ? <div role="alert" className="my-5 space-y-3 border-l-4 border-[#DC4545] pl-3 text-sm text-[#10243E]"><p>{section.error}</p><button type="button" className={button} onClick={retry}>Retry {title.toLowerCase()}</button></div> : section.data ? children : <p className="py-5 text-sm text-[#64748B]">Data unavailable.</p>}
  </section>;
}
function PreviewNote({ data }) { return <p className="mt-4 text-xs text-[#64748B]">Showing {data.items.length} of {data.total} records.</p>; }
export function CustomerDashboardView({ state, actions, displayName }) {
  const summary = state.summary.data;
  const cards = [["Outstanding Credit", summary ? formatCustomerMoney(summary.total_outstanding_balance) : "—", Wallet, "Across your linked credit accounts"], ["My Shops", summary?.linked_shop_count ?? "—", Store, "Securely linked shops"], ["Credit Accounts", summary?.credit_account_count ?? "—", CreditCard, "Your accessible accounts"], ["Recent Activity", summary ? summary.recent_activity.length : "—", History, "Records among your latest 5 transactions"]];
  const busy = ["summary", "shops", "accounts", "transactions"].some(key => state[key].loading);
  return <div className="space-y-7 pb-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><h2 className="break-words text-2xl font-bold">Welcome, {displayName || "Customer"}!</h2><p className="mt-2 text-sm text-[#64748B]">Your linked shops and credit records at a glance.</p></div><button type="button" className={button} disabled={busy} onClick={actions.start}><RefreshCw size={17} aria-hidden="true" />Refresh dashboard</button></div>
    {state.authError ? <p role="alert" className="rounded-xl border border-[#DC4545] bg-white p-5 text-sm text-[#10243E]">{state.authError}</p> : <>
      <section aria-label="Customer overview">
        {state.summary.loading && <Loading>Loading your account summary...</Loading>}
        {state.summary.error && <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 border-l-4 border-[#DC4545] pl-3 text-sm text-[#10243E]"><p>{state.summary.error}</p><button type="button" className={button} onClick={() => actions.load("summary")}>Retry summary</button></div>}
        <div className="grid min-w-0 gap-5 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([title, value, Icon, detail]) => <article key={title} className={card}><div className="flex items-start justify-between gap-3"><h3 className="text-sm font-semibold">{title}</h3><span className="rounded-xl bg-[#E8F8F6] p-2 text-[#12B8A6]"><Icon size={20} aria-hidden="true" /></span></div><p className="mt-5 break-words text-2xl font-bold [overflow-wrap:anywhere]">{value}</p><p className="mt-2 text-xs text-[#64748B]">{summary ? detail : state.summary.loading ? "Loading..." : "Summary unavailable"}</p></article>)}</div>
      </section>
      <Section id="my-shops" title="My Shops" section={state.shops} retry={() => actions.load("shops")}>
        {state.shops.data && (state.shops.data.items.length ? <><ul className="mt-5 grid min-w-0 gap-4 md:grid-cols-2">{state.shops.data.items.map(shop => <li key={shop.business_id} className="min-w-0 rounded-xl border border-[#E1EAF4] p-4"><h3 className="break-words font-semibold">{shop.business_name}</h3><p className="mt-2 text-sm text-[#64748B]">{shop.credit_account_count ? shop.credit_account_count + " credit account(s)" : "No credit account at this shop yet."}</p><p className="mt-3 break-words font-semibold [overflow-wrap:anywhere]">Outstanding: {formatCustomerMoney(shop.outstanding_balance)}</p></li>)}</ul><PreviewNote data={state.shops.data} /></> : <div className="py-6 text-sm text-[#64748B]"><p>No shops are linked to your account yet.</p><p className="mt-2">Your shop records will appear after your account is securely linked. Matching contact details alone do not link records.</p></div>)}
      </Section>
      <Section id="my-credit" title="My Credit Accounts" section={state.accounts} retry={() => actions.load("accounts")}>
        {state.accounts.data && (state.accounts.data.items.length ? <><ul className="mt-5 grid min-w-0 gap-4 md:grid-cols-2">{state.accounts.data.items.map(account => <li key={account.credit_account_id} className="min-w-0 rounded-xl border border-[#E1EAF4] p-4"><div className="flex flex-wrap items-start justify-between gap-2"><h3 className="break-words font-semibold">{account.business_name}</h3><span className={"rounded-full px-2.5 py-1 text-xs font-semibold capitalize " + (account.account_status === "active" ? "bg-[#22C55E]/10 text-[#10243E]" : account.account_status === "suspended" ? "bg-[#F5B544]/15 text-[#10243E]" : "bg-[#F5F8FC] text-[#64748B]")}>{account.account_status}</span></div><p className="mt-2 text-xs text-[#64748B]">Account #{account.credit_account_id}</p><dl className="mt-4 space-y-3 text-sm"><div><dt className="text-[#64748B]">Outstanding balance</dt><dd className="mt-1 break-words text-lg font-bold [overflow-wrap:anywhere]">{formatCustomerMoney(account.outstanding_balance)}</dd></div><div><dt className="text-[#64748B]">Credit limit</dt><dd className="mt-1 break-words font-semibold [overflow-wrap:anywhere]">{formatCustomerMoney(account.credit_limit)}</dd></div></dl></li>)}</ul><PreviewNote data={state.accounts.data} /></> : <p className="py-6 text-sm text-[#64748B]">No credit accounts are linked to your account yet.</p>)}
      </Section>
      <Section id="transactions" title="Recent Transactions" section={state.transactions} retry={() => actions.load("transactions")}>
        {state.transactions.data && (state.transactions.data.items.length ? <><p className="mt-2 text-xs text-[#64748B]">Newest records first. A repayment record does not independently verify bank or card settlement.</p><ul className="mt-5 divide-y divide-[#E1EAF4]">{state.transactions.data.items.map(row => <li key={row.entry_id} className="grid min-w-0 gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{typeLabel[row.entry_type]}</h3>{row.status !== "recorded" && <span className="rounded-full bg-[#F5B544]/15 px-2 py-1 text-xs capitalize">{row.status}</span>}</div><p className="mt-1 break-words text-sm">{row.business_name}</p><p className="mt-1 break-all text-xs text-[#64748B]">{row.reference}</p><time dateTime={row.recorded_at} className="mt-1 block text-xs text-[#64748B]" title="Recorded time">{formatRecordedTime(row.recorded_at)}</time></div><div className="min-w-0 sm:max-w-64 sm:text-right"><p className="break-words font-bold [overflow-wrap:anywhere]">{formatCustomerMoney(row.amount)}</p>{row.entry_type === "reversal" && <p className="mt-1 break-words text-xs text-[#64748B] [overflow-wrap:anywhere]">Balance adjustment: {formatCustomerMoney(row.balance_delta)}</p>}</div></li>)}</ul><PreviewNote data={state.transactions.data} /></> : <p className="py-6 text-sm text-[#64748B]">No transactions to display yet.</p>)}
      </Section>
    </>}
  </div>;
}
function CustomerDashboardSession({ displayName }) {
  const [reader] = useState(() => createCustomerDashboardReader({ summary: getCustomerSummary, shops: getCustomerShops, accounts: getCustomerCreditAccounts, transactions: getCustomerTransactions }));
  const state = useSyncExternalStore(reader.subscribe, reader.getSnapshot, reader.getSnapshot);
  useEffect(() => { reader.start(); return () => reader.dispose(); }, [reader]);
  return <CustomerDashboardView state={state} actions={reader} displayName={displayName} />;
}
export default function CustomerDashboard() {
  const { user, token, isAuthenticated } = useAuth();
  if (!isAuthenticated || user?.platform_role !== "customer") return null;
  return <CustomerDashboardSession key={user.user_id + ":" + token} displayName={user.full_name} />;
}
