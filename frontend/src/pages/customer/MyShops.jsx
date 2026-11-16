import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useCustomerRead } from "../../hooks/useCustomerRead";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Store, ChevronDown } from "lucide-react";
import { useAuth } from "../../context/useAuth";
import { getCustomerSummary, getMyShops, getShopCreditAccounts } from "../../services/customerDashboardService";
import { parseCustomerResponse, formatCustomerMoney } from "../../utils/customerDashboard";
import { parseCustomerPage } from "../../utils/customerAccounts";
import { CustomerDataState, CustomerPagination, customerButton, customerCard } from "../../components/customer/CustomerData";
import CustomerJoinRequests from "../../components/customer/CustomerJoinRequests";

export function ShopAccountChoices({ state, retry, page, onPage }) {
  const { tr } = useAppTranslation();
  return <div className="mt-4 border-t border-[#E1EAF4] pt-4"><CustomerDataState state={state} retry={retry} label={tr("shop accounts")}>
    {state.data && (state.data.items.length ? <><p className="mb-3 text-sm text-[#64748B]">{tr("Choose the credit account you want to view. Account status and available credit come from your shop's current credit records.")}</p><ul className="space-y-3">{state.data.items.map(account => <li key={account.credit_account_id} className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-lg border border-[#E1EAF4] p-3"><div className="min-w-0"><p className="font-semibold">{tr("Account #")}{account.credit_account_id}</p><p className="mt-1 break-words text-xs capitalize text-[#64748B]">{tr("Status:")} {tr(account.account_status)}</p><p className="mt-2 break-words text-sm [overflow-wrap:anywhere]">{tr("Outstanding:")} {formatCustomerMoney(account.outstanding_balance)}</p><p className="mt-1 break-words text-sm [overflow-wrap:anywhere]">{tr("Available credit:")} {formatCustomerMoney(account.available_credit)}</p></div><Link to={"/customer/credit/" + account.credit_account_id} className={customerButton}>{tr("View account #")}{account.credit_account_id}</Link></li>)}</ul></> : <p className="py-3 text-sm text-[#64748B]">{tr("No credit accounts are available for this shop.")}</p>)}
  </CustomerDataState><CustomerPagination page={page} total={state.data?.total ?? null} loading={state.loading} onPage={onPage} /></div>;
}
function ShopAccountPage({ businessId, page, onPage, onDenied }) {
  const [state, reader] = useCustomerRead(options => getShopCreditAccounts(businessId, page, options), data => parseCustomerPage("accounts", data, page, { businessId }), onDenied);
  return <ShopAccountChoices state={state} retry={reader.load} page={page} onPage={onPage} />;
}
function ShopCard({ shop, onDenied }) {
  const { tr } = useAppTranslation();
  const [expanded, setExpanded] = useState(false), [page, setPage] = useState(1);
  return <article className={customerCard}><div className="flex items-start gap-3"><span className="rounded-xl bg-[#E8F8F6] p-2 text-[#12B8A6]"><Store size={22} aria-hidden="true" /></span><div className="min-w-0"><h3 className="break-words text-lg font-bold">{shop.business_name}</h3><p className="mt-1 text-xs text-[#64748B]">{tr("Shop #")}{shop.business_id}</p></div></div><p className="mt-4 text-sm text-[#64748B]">{tr("Connected shop ·")} {shop.credit_account_count} {tr("linked credit account(s)")}</p><p className="mt-2 break-words font-semibold [overflow-wrap:anywhere]">{tr("Outstanding:")} {formatCustomerMoney(shop.outstanding_balance)}</p>
    {shop.credit_account_count === 0 ? <p className="mt-4 text-sm text-[#64748B]">{tr("No credit account at this shop yet. Shop connection alone does not enable credit purchases.")}</p> : <><p className="mt-3 text-xs text-[#64748B]">{tr("Credit purchasing depends on your account status and available credit shown in account details.")}</p><button type="button" className={customerButton + " mt-4"} aria-expanded={expanded} aria-controls={"shop-accounts-" + shop.business_id} onClick={() => setExpanded(value => !value)}>{expanded ? tr("Hide accounts") : tr("View Details")}<ChevronDown size={16} aria-hidden="true" /></button></>}
    {expanded && <div id={"shop-accounts-" + shop.business_id}><ShopAccountPage key={page} businessId={shop.business_id} page={page} onPage={setPage} onDenied={onDenied} /></div>}
  </article>;
}
export function MyShopsView({ summary, shops, retrySummary, retryShops, page, onPage, onDenied }) {
  const { tr } = useAppTranslation();
  return <div className="space-y-6 pb-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-2xl font-bold">{tr("My Shops")}</h2><p className="mt-2 text-sm text-[#64748B]">{tr("Businesses securely linked to your customer account.")}</p></div><button type="button" className={customerButton} onClick={() => { retryShops(); retrySummary(); }}>{tr("Refresh shops")}</button></div>
    <section aria-label={tr("My Shops summary")} className={customerCard}><CustomerDataState state={summary} retry={retrySummary} label={tr("shop summary")}><div className="grid min-w-0 gap-5 sm:grid-cols-2"><div><h3 className="text-sm text-[#64748B]">{tr("Total Linked Shops")}</h3><p className="mt-2 text-2xl font-bold">{summary.data?.linked_shop_count ?? "—"}</p></div><div><h3 className="text-sm text-[#64748B]">{tr("Total Outstanding Credit")}</h3><p className="mt-2 break-words text-2xl font-bold [overflow-wrap:anywhere]">{summary.data ? formatCustomerMoney(summary.data.total_outstanding_balance) : "—"}</p></div></div></CustomerDataState></section>
    <section aria-label={tr("Linked shops")}><CustomerDataState state={shops} retry={retryShops} label={tr("linked shops")}>{shops.data && (shops.data.items.length ? <div className="grid min-w-0 items-start gap-5 xl:grid-cols-2">{shops.data.items.map(shop => <ShopCard key={shop.business_id} shop={shop} onDenied={onDenied} />)}</div> : <p className={customerCard + " text-sm text-[#64748B]"}>{shops.data.total === 0 ? tr("No shops are linked to your account yet.") : tr("No shops on this page. Use Previous to return to your shops.")}</p>)}</CustomerDataState><CustomerPagination page={page} total={shops.data?.total ?? null} loading={shops.loading} onPage={onPage} /></section>
  </div>;
}
function ShopListPage({ summary, retrySummary, page, onPage, onDenied }) {
  const [shops, reader] = useCustomerRead(options => getMyShops(page, options), data => parseCustomerPage("shops", data, page), onDenied);
  useEffect(() => {
    const refresh = () => { reader.load(); retrySummary(); };
    const whenVisible = () => { if (document.visibilityState === "visible") refresh(); };
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", whenVisible);
    return () => { window.removeEventListener("focus", refresh); document.removeEventListener("visibilitychange", whenVisible); };
  }, [reader, retrySummary]);
  return <MyShopsView summary={summary} shops={shops} retrySummary={retrySummary} retryShops={reader.load} page={page} onPage={onPage} onDenied={onDenied} />;
}
function MyShopsSession() {
  const { tr } = useAppTranslation();
  const [page, setPage] = useState(1), [accessError, setAccessError] = useState("");
  const [summary, reader] = useCustomerRead(getCustomerSummary, data => parseCustomerResponse("summary", data), setAccessError);
  if (accessError) return <p role="alert" className={customerCard + " border-l-4 border-l-[#DC4545]"}>{tr(accessError)}</p>;
  return <div className="space-y-6"><ShopListPage key={page} summary={summary} retrySummary={reader.load} page={page} onPage={setPage} onDenied={setAccessError} /><CustomerJoinRequests /></div>;
}
export default function MyShops() {
  const { user, token, isAuthenticated } = useAuth();
  return isAuthenticated && user?.platform_role === "customer" ? <MyShopsSession key={user.user_id + ":" + token} /> : null;
}
