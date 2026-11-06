import { useCustomerRead } from "../../hooks/useCustomerRead";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Store, ChevronDown } from "lucide-react";
import { useAuth } from "../../context/useAuth";
import { getCustomerSummary, getMyShops, getShopCreditAccounts } from "../../services/customerDashboardService";
import { parseCustomerResponse, formatCustomerMoney } from "../../utils/customerDashboard";
import { parseCustomerPage } from "../../utils/customerAccounts";
import { CustomerDataState, CustomerPagination, customerButton, customerCard } from "../../components/customer/CustomerData";

export function ShopAccountChoices({ state, retry, page, onPage }) {
  return <div className="mt-4 border-t border-[#E1EAF4] pt-4"><CustomerDataState state={state} retry={retry} label="shop accounts">
    {state.data && (state.data.items.length ? <><p className="mb-3 text-sm text-[#64748B]">Choose the credit account you want to view.</p><ul className="space-y-3">{state.data.items.map(account => <li key={account.credit_account_id} className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-lg border border-[#E1EAF4] p-3"><div className="min-w-0"><p className="font-semibold">Account #{account.credit_account_id}</p><p className="mt-1 break-words text-xs capitalize text-[#64748B]">Status: {account.account_status}</p><p className="mt-2 break-words text-sm [overflow-wrap:anywhere]">Outstanding: {formatCustomerMoney(account.outstanding_balance)}</p></div><Link to={"/customer/credit/" + account.credit_account_id} className={customerButton}>View account #{account.credit_account_id}</Link></li>)}</ul></> : <p className="py-3 text-sm text-[#64748B]">No credit accounts are available for this shop.</p>)}
  </CustomerDataState><CustomerPagination page={page} total={state.data?.total ?? null} loading={state.loading} onPage={onPage} /></div>;
}
function ShopAccountPage({ businessId, page, onPage, onDenied }) {
  const [state, reader] = useCustomerRead(options => getShopCreditAccounts(businessId, page, options), data => parseCustomerPage("accounts", data, page, { businessId }), onDenied);
  return <ShopAccountChoices state={state} retry={reader.load} page={page} onPage={onPage} />;
}
function ShopCard({ shop, onDenied }) {
  const [expanded, setExpanded] = useState(false), [page, setPage] = useState(1);
  return <article className={customerCard}><div className="flex items-start gap-3"><span className="rounded-xl bg-[#E8F8F6] p-2 text-[#12B8A6]"><Store size={22} aria-hidden="true" /></span><div className="min-w-0"><h3 className="break-words text-lg font-bold">{shop.business_name}</h3><p className="mt-1 text-xs text-[#64748B]">Shop #{shop.business_id}</p></div></div><p className="mt-4 text-sm text-[#64748B]">{shop.credit_account_count} linked credit account(s)</p><p className="mt-2 break-words font-semibold [overflow-wrap:anywhere]">Outstanding: {formatCustomerMoney(shop.outstanding_balance)}</p>
    {shop.credit_account_count === 0 ? <p className="mt-4 text-sm text-[#64748B]">No credit account at this shop yet.</p> : <button type="button" className={customerButton + " mt-4"} aria-expanded={expanded} aria-controls={"shop-accounts-" + shop.business_id} onClick={() => setExpanded(value => !value)}>{expanded ? "Hide accounts" : "View Details"}<ChevronDown size={16} aria-hidden="true" /></button>}
    {expanded && <div id={"shop-accounts-" + shop.business_id}><ShopAccountPage key={page} businessId={shop.business_id} page={page} onPage={setPage} onDenied={onDenied} /></div>}
  </article>;
}
export function MyShopsView({ summary, shops, retrySummary, retryShops, page, onPage, onDenied }) {
  return <div className="space-y-6 pb-6"><div><h2 className="text-2xl font-bold">My Shops</h2><p className="mt-2 text-sm text-[#64748B]">Businesses securely linked to your customer account.</p></div>
    <section aria-label="My Shops summary" className={customerCard}><CustomerDataState state={summary} retry={retrySummary} label="shop summary"><div className="grid min-w-0 gap-5 sm:grid-cols-2"><div><h3 className="text-sm text-[#64748B]">Total Linked Shops</h3><p className="mt-2 text-2xl font-bold">{summary.data?.linked_shop_count ?? "—"}</p></div><div><h3 className="text-sm text-[#64748B]">Total Outstanding Credit</h3><p className="mt-2 break-words text-2xl font-bold [overflow-wrap:anywhere]">{summary.data ? formatCustomerMoney(summary.data.total_outstanding_balance) : "—"}</p></div></div></CustomerDataState></section>
    <section aria-label="Linked shops"><CustomerDataState state={shops} retry={retryShops} label="linked shops">{shops.data && (shops.data.items.length ? <div className="grid min-w-0 items-start gap-5 xl:grid-cols-2">{shops.data.items.map(shop => <ShopCard key={shop.business_id} shop={shop} onDenied={onDenied} />)}</div> : <p className={customerCard + " text-sm text-[#64748B]"}>{shops.data.total === 0 ? "No shops are linked to your account yet." : "No shops on this page. Use Previous to return to your shops."}</p>)}</CustomerDataState><CustomerPagination page={page} total={shops.data?.total ?? null} loading={shops.loading} onPage={onPage} /></section>
  </div>;
}
function ShopListPage({ summary, retrySummary, page, onPage, onDenied }) {
  const [shops, reader] = useCustomerRead(options => getMyShops(page, options), data => parseCustomerPage("shops", data, page), onDenied);
  return <MyShopsView summary={summary} shops={shops} retrySummary={retrySummary} retryShops={reader.load} page={page} onPage={onPage} onDenied={onDenied} />;
}
function MyShopsSession() {
  const [page, setPage] = useState(1), [accessError, setAccessError] = useState("");
  const [summary, reader] = useCustomerRead(getCustomerSummary, data => parseCustomerResponse("summary", data), setAccessError);
  if (accessError) return <p role="alert" className={customerCard + " border-l-4 border-l-[#DC4545]"}>{accessError}</p>;
  return <ShopListPage key={page} summary={summary} retrySummary={reader.load} page={page} onPage={setPage} onDenied={setAccessError} />;
}
export default function MyShops() {
  const { user, token, isAuthenticated } = useAuth();
  return isAuthenticated && user?.platform_role === "customer" ? <MyShopsSession key={user.user_id + ":" + token} /> : null;
}
