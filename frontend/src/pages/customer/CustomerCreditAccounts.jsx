import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Store, FileText } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { useCustomerRead } from '../../hooks/useCustomerRead';
import { getCustomerSummary,getMyCreditAccounts,getCustomerTransactions } from '../../services/customerDashboardService';
import { parseCustomerResponse,formatCustomerMoney,formatRecordedTime } from '../../utils/customerDashboard';
import { parseCustomerPage } from '../../utils/customerAccounts';
import { CustomerDataState,CustomerPagination,customerCard,customerButton } from '../../components/customer/CustomerData';
import CustomerCreditOverview from '../../components/customer/CustomerCreditOverview';
import { AccountSession } from './CreditAccountDetails';

export function CustomerCreditAccountsView({summary,accounts,transactions,retrySummary,retryAccounts,retryTransactions,page,onPage,selected,onSelect,children}) {
  const { tr } = useAppTranslation();
  return <div className="space-y-5"><div className="flex flex-wrap items-center justify-between gap-4"><div><h2>{tr("My Credit Accounts")}</h2><p className="mt-2 text-sm text-[#52698A]">{tr("View your outstanding balances and credit transactions across shops.")}</p></div>{selected?<Link className={customerButton} to={'/customer/credit/'+selected+'/statement'}><FileText size={18}/>{tr("View / Download Statement")}</Link>:<p className="text-xs text-[#64748B]">{tr("Select an account to view its statement.")}</p>}</div>
    <CustomerDataState state={summary} retry={retrySummary} label={tr("credit summary")}><CustomerCreditOverview summary={summary.data}/></CustomerDataState>
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(210px,1fr)]"><section className={customerCard}><h3 className="text-xl font-bold">{tr("Your Shop Balances")}</h3><p className="mt-1 text-sm text-[#52698A]">{tr("Select a credit account to view its ledger and transactions.")}</p><CustomerDataState state={accounts} retry={retryAccounts} label={tr("credit accounts")}>{accounts.data&&(accounts.data.items.length?<ul className="mt-4 space-y-2">{accounts.data.items.map(account=><li key={account.credit_account_id}><button type="button" onClick={()=>onSelect(account.credit_account_id)} aria-pressed={selected===account.credit_account_id} className={'flex w-full flex-wrap items-center gap-4 rounded-xl border p-4 text-left '+(selected===account.credit_account_id?'border-[#12B8A6] bg-[#EDFAF9]':'border-[#E1EAF4] bg-white')}><span className="rounded-full bg-[#E7F9F6] p-3 text-[#008C87]"><Store size={22} aria-hidden="true"/></span><span className="min-w-0 flex-1"><span className="block break-words font-semibold">{account.business_name}</span><span className="mt-1 block text-xs text-[#64748B]">{tr("Account #")}{account.credit_account_id} · {tr(account.account_status)}</span></span><span className="font-bold">{formatCustomerMoney(account.outstanding_balance)}</span><span className="text-xs text-[#64748B]">{tr("Due date unavailable")}</span></button></li>)}</ul>:<p className="py-6 text-sm text-[#64748B]">{tr("No credit accounts are linked to your account yet.")}</p>)}</CustomerDataState><CustomerPagination page={page} total={accounts.data?.total??null} loading={accounts.loading} onPage={onPage}/></section><aside className={customerCard}><FileText size={38} className="text-[#12B8A6]" aria-hidden="true"/><h3 className="mt-4 text-lg font-bold">{tr("Need help with your credit account?")}</h3><p className="mt-2 text-sm text-[#52698A]">{tr("Review the recorded transactions and account statement.")}</p><Link className={customerButton+' mt-4'} to="/customer/transactions">{tr("View Full History")}</Link><p className="mt-3 text-xs text-[#64748B]">{tr("In-app support messaging is not available.")}</p></aside></div>
    {children}
    <section className={customerCard}><h3 className="text-xl font-bold">{tr("Recent Transactions")}</h3><p className="mt-1 text-xs text-[#64748B]">{tr("Latest records across your accounts. Per-account running balances are available in statements.")}</p><CustomerDataState state={transactions} retry={retryTransactions} label={tr("recent transactions")}>{transactions.data&&(transactions.data.items.length?<div className="customer-table-wrap"><table><thead><tr>{['Date','Shop','Transaction','Reference','Amount'].map(label=><th key={label}>{tr(label)}</th>)}</tr></thead><tbody>{transactions.data.items.map(row=><tr key={row.entry_id}><td>{formatRecordedTime(row.recorded_at)}</td><td>{row.business_name}</td><td>{tr(row.entry_type)} · {tr(row.status)}</td><td>{row.reference}</td><td className="font-semibold">{formatCustomerMoney(row.amount)}</td></tr>)}</tbody></table></div>:<p className="py-5 text-sm text-[#64748B]">{tr("No transactions to display yet.")}</p>)}</CustomerDataState></section>
  </div>;
}
function AccountPage({summary,retrySummary,transactions,retryTransactions,page,onPage,selected,onSelect,onDenied}) {
  const [accounts,reader]=useCustomerRead(options=>getMyCreditAccounts(page,options),data=>parseCustomerPage('accounts',data,page),onDenied);
  return <CustomerCreditAccountsView {...{summary,retrySummary,transactions,retryTransactions,accounts,page,onPage,selected,onSelect}} retryAccounts={reader.load}>{selected&&<AccountSession key={selected} accountId={selected} onDenied={onDenied}/>}</CustomerCreditAccountsView>;
}
function Session() {
  const { tr } = useAppTranslation();
  const [page,setPage]=useState(1),[selected,setSelected]=useState(null),[denied,setDenied]=useState('');
  const [summary,reader]=useCustomerRead(getCustomerSummary,data=>parseCustomerResponse('summary',data),setDenied);
  const [transactions,history]=useCustomerRead(getCustomerTransactions,data=>parseCustomerResponse('transactions',data),setDenied);
  if(denied)return <p role="alert" className={customerCard}>{tr(denied)}</p>;
  return <AccountPage key={page} {...{summary,transactions,page,selected}} retrySummary={reader.load} retryTransactions={history.load} onPage={setPage} onSelect={setSelected} onDenied={setDenied}/>;
}
export default function CustomerCreditAccounts() {
  const {user,token,isAuthenticated}=useAuth();
  return isAuthenticated&&user?.platform_role==='customer'?<Session key={user.user_id+':'+token}/>:null;
}
