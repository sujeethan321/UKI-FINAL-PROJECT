import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useCustomerRead } from "../../hooks/useCustomerRead";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useAuth } from "../../context/useAuth";
import { getCustomerAccountDetail, getAccountTransactions } from "../../services/customerDashboardService";
import { parseAccountId, parseAccountDetail, parseCustomerPage } from "../../utils/customerAccounts";
import { formatCustomerMoney, formatRecordedTime } from "../../utils/customerDashboard";
import { CustomerDataState, CustomerPagination, customerButton, customerCard } from "../../components/customer/CustomerData";

export function AccountActivityView({ state, retry, page, onPage }) {
  const { tr } = useAppTranslation();
  return <section className={customerCard} aria-labelledby="account-activity-heading"><h3 id="account-activity-heading" className="text-xl font-bold">{tr("Recent Credit Activity")}</h3><p className="mt-2 text-xs text-[#64748B]">{tr("Newest records first. Repayment records do not independently verify bank or card settlement.")}</p><CustomerDataState state={state} retry={retry} label={tr("account activity")}>{state.data && (state.data.items.length ? <ul className="mt-4 divide-y divide-[#E1EAF4]">{state.data.items.map(row => <li key={row.entry_id} className="grid min-w-0 gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0"><p className="font-semibold">{tr({ credit_sale: "Credit sale", repayment: "Repayment record", reversal: "Reversal" }[row.entry_type])}{row.status !== "recorded" && <span className="ml-2 rounded-full bg-[#F5B544]/15 px-2 py-1 text-xs capitalize">{tr(row.status)}</span>}</p><p className="mt-1 break-all text-xs text-[#64748B]">{row.reference}</p><time dateTime={row.recorded_at} className="mt-1 block text-xs text-[#64748B]">{formatRecordedTime(row.recorded_at)}</time></div><div className="min-w-0 sm:max-w-64 sm:text-right"><p className="break-words font-bold [overflow-wrap:anywhere]">{formatCustomerMoney(row.amount)}</p>{row.entry_type === "reversal" && <p className="mt-1 break-words text-xs text-[#64748B] [overflow-wrap:anywhere]">{tr("Balance adjustment:")} {formatCustomerMoney(row.balance_delta)}</p>}</div></li>)}</ul> : <p className="py-6 text-sm text-[#64748B]">{state.data.total === 0 ? tr("No transactions for this account yet.") : tr("No transactions on this page.")}</p>)}</CustomerDataState><CustomerPagination page={page} total={state.data?.total ?? null} loading={state.loading} onPage={onPage} /></section>;
}
function AccountActivity({ accountId, businessId, page, onPage, onDenied }) {
  const [state, reader] = useCustomerRead(options => getAccountTransactions(accountId, page, options), data => parseCustomerPage("transactions", data, page, { accountId, businessId }), onDenied);
  return <AccountActivityView state={state} retry={reader.load} page={page} onPage={onPage} />;
}
export function AccountDetailsView({ state, retry, children }) {
  const { tr } = useAppTranslation();
  const account = state.data;
  return <div className="space-y-6 pb-6"><Link to="/customer/shops" className={customerButton}><ArrowLeft size={17} aria-hidden="true" />{tr("Back to My Shops")}</Link><h2 className="text-2xl font-bold">{tr("Credit Account Details")}</h2><CustomerDataState state={state} retry={retry} label={tr("credit account")}>{account && <><section className={customerCard}><h3 className="break-words text-xl font-bold">{account.business_name}</h3><p className="mt-2 text-sm text-[#64748B]">{tr("Account #")}{account.credit_account_id} {tr("· Shop #")}{account.business_id}</p><div className="mt-4 flex flex-wrap gap-3"><Link className={customerButton} to={"/customer/transactions?accountId=" + account.credit_account_id}>{tr("Transaction history")}</Link><Link className={customerButton} to={"/customer/credit/" + account.credit_account_id + "/statement"}>{tr("View credit statement")}</Link></div><p className="mt-3 text-sm">{tr("Account status:")} <span className="rounded-full bg-[#F5F8FC] px-3 py-1 font-semibold capitalize">{tr(account.account_status)}</span></p></section><div className="grid min-w-0 gap-5 sm:grid-cols-2 xl:grid-cols-3">{[["Outstanding Balance", account.outstanding_balance], ["Credit Limit", account.credit_limit], ["Available Credit", account.available_credit]].map(([label, value]) => <section className={customerCard} key={label}><h3 className="text-sm text-[#64748B]">{tr(label)}</h3><p className="mt-3 break-words text-2xl font-bold [overflow-wrap:anywhere]">{formatCustomerMoney(value)}</p></section>)}</div><p className="text-xs text-[#64748B]">{tr("Available credit is the shop ledger's current allowance. Account status and shop approval still determine permitted activity.")}</p>{children}</>}</CustomerDataState></div>;
}
export function AccountSession({ accountId, onDenied }) {
  const { tr } = useAppTranslation();
  const [page, setPage] = useState(1), [accessError, setAccessError] = useState("");
  const deny = message => { setAccessError(message); onDenied?.(message); };
  const [state, reader] = useCustomerRead(options => getCustomerAccountDetail(accountId, options), data => parseAccountDetail(data, accountId), deny);
  if (accessError) return <div className="space-y-4"><Link to="/customer/shops" className={customerButton}>{tr("Back to My Shops")}</Link><p role="alert" className={customerCard + " border-l-4 border-l-[#DC4545]"}>{tr(accessError)}</p></div>;
  return <AccountDetailsView state={state} retry={reader.load}>{state.data && <AccountActivity key={page} accountId={accountId} businessId={state.data.business_id} page={page} onPage={setPage} onDenied={deny} />}</AccountDetailsView>;
}
export default function CreditAccountDetails() {
  const { tr } = useAppTranslation();
  const { accountId: rawId } = useParams();
  const { user, token, isAuthenticated } = useAuth();
  const accountId = parseAccountId(rawId);
  if (!isAuthenticated || user?.platform_role !== "customer") return null;
  if (accountId === null) return <div className="space-y-4"><Link to="/customer/shops" className={customerButton}>{tr("Back to My Shops")}</Link><p role="alert" className={customerCard}>{tr("This record is not available to your account. Please return to My Shops.")}</p></div>;
  return <AccountSession key={user.user_id + ":" + token + ":" + accountId} accountId={accountId} />;
}
