import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import { useCustomerRead } from '../../hooks/useCustomerRead';
import { getMyShops, getTransactionHistory } from '../../services/customerDashboardService';
import { parseAccountId, parseCustomerPage } from '../../utils/customerAccounts';
import { historyParams, parseHistory, validPeriod } from '../../utils/customerHistory';
import { formatCustomerMoney, formatRecordedTime } from '../../utils/customerDashboard';
import { CustomerDataState, CustomerPagination, customerButton, customerCard } from '../../components/customer/CustomerData';

export function TransactionRows({state,retry,page,onPage}) {
  return <section className={customerCard} aria-label="Transaction results"><CustomerDataState state={state} retry={retry} label="transactions">{state.data && (state.data.items.length ? <ul className="divide-y divide-[#D4E2EE]">{state.data.items.map(row=><li key={row.entry_id} className="min-w-0 py-4"><div className="grid min-w-0 gap-3 sm:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0"><p className="font-bold">{{credit_sale:'Credit sale',repayment:'Repayment record',reversal:'Reversal'}[row.entry_type]} <span className="rounded-full bg-[#E8F8F6] px-2 py-1 text-xs capitalize">{row.status}</span></p><p className="mt-2 break-words">{row.business_name}</p><p className="mt-1 break-all text-sm">{row.reference}</p><time className="text-xs text-[#64748B]" dateTime={row.recorded_at}>{formatRecordedTime(row.recorded_at)}</time></div><p className="break-words font-bold [overflow-wrap:anywhere]">{formatCustomerMoney(row.amount)}</p></div><details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold">View transaction details</summary><div className="mt-3 space-y-2"><p className="break-all">Reference: {row.reference}</p><p>Account #{row.credit_account_id} · Shop #{row.business_id}</p><p>Status: {row.status}</p><p className="break-words [overflow-wrap:anywhere]">Balance adjustment: {formatCustomerMoney(row.balance_delta)}</p><div className="flex flex-wrap gap-3"><Link className={customerButton} to={'/customer/credit/'+row.credit_account_id}>Account details</Link><Link className={customerButton} to={'/customer/credit/'+row.credit_account_id+'/statement'}>Credit statement</Link></div></div></details></li>)}</ul> : <p className="py-6 text-sm text-[#64748B]">No transactions match these filters. Unlinked accounts have no accessible records.</p>)}</CustomerDataState><CustomerPagination page={page} total={state.data?.total??null} loading={state.loading} onPage={onPage}/></section>;
}
function HistoryPage({filters,accountId,page,onPage,onDenied}) {
  const [state,reader]=useCustomerRead(options=>getTransactionHistory(historyParams(filters,accountId),page,options),data=>parseHistory(data,page,filters,accountId),onDenied);
  return <TransactionRows state={state} retry={reader.load} page={page} onPage={onPage}/>;
}
function ShopOptions({page,onPage,onChoose,onDenied}) {
  const [state,reader]=useCustomerRead(options=>getMyShops(page,options),data=>parseCustomerPage('shops',data,page),onDenied);
  return <div className="mt-3"><CustomerDataState state={state} retry={reader.load} label="shop filter choices">{state.data && <div className="flex flex-wrap gap-2">{state.data.items.map(shop=><button key={shop.business_id} type="button" className={customerButton} onClick={()=>onChoose(shop)}>{shop.business_name} (#{shop.business_id})</button>)}{state.data.total===0 && <p className="text-sm">No shops are linked to your account yet.</p>}</div>}</CustomerDataState><CustomerPagination page={page} total={state.data?.total??null} loading={state.loading} onPage={onPage}/></div>;
}
export function HistoryFilters({filters,onChange,shopLabel,onAllShops,children}) {
  return <section className={customerCard} aria-label="Transaction filters"><h3 className="font-bold">Filters</h3><p className="mt-2 break-words text-sm">Shop: {shopLabel || 'All linked shops'}</p><button type="button" className={customerButton+' mt-3'} onClick={onAllShops}>All linked shops</button>{children}<div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3"><label className="text-sm">Transaction type<select className="mt-2 block w-full rounded-lg border border-[#D4E2EE] bg-white p-2" value={filters.entry_type} onChange={e=>onChange('entry_type',e.target.value)}><option value="">All types (including reversals)</option><option value="credit_sale">Credit sales</option><option value="repayment">Repayments</option></select></label>{[['Start date','start_date'],['End date','end_date']].map(([label,key])=><label key={key} className="text-sm">{label}<input className="mt-2 block w-full rounded-lg border border-[#D4E2EE] p-2" type="date" value={filters[key]} onChange={e=>onChange(key,e.target.value)}/></label>)}</div><p className="mt-3 text-xs text-[#64748B]">Inclusive dates use the database recorded clock, without timezone conversion. Repayment records do not independently verify bank or card settlement.</p></section>;
}
function HistorySession({accountId}) {
  const [filters,setFilters]=useState({business_id:'',entry_type:'',start_date:'',end_date:''}),[shopLabel,setShopLabel]=useState(''),[page,setPage]=useState(1),[shopPage,setShopPage]=useState(1),[accessError,setAccessError]=useState('');
  const change=(key,value)=>{setFilters(old=>({...old,[key]:value}));setPage(1);};
  if(accessError)return <p role="alert" className={customerCard}>{accessError}</p>;
  const valid=validPeriod(filters.start_date,filters.end_date);
  return <div className="space-y-6"><h2 className="text-2xl font-bold">Transaction History</h2>{accountId && <p>Viewing account #{accountId}. <Link className="underline" to="/customer/transactions">All my accounts</Link></p>}<HistoryFilters filters={filters} onChange={change} shopLabel={shopLabel} onAllShops={()=>{change('business_id','');setShopLabel('');}}><ShopOptions key={shopPage} page={shopPage} onPage={setShopPage} onDenied={setAccessError} onChoose={shop=>{change('business_id',String(shop.business_id));setShopLabel(shop.business_name);}}/></HistoryFilters>{valid ? <HistoryPage key={JSON.stringify([filters,accountId,page])} filters={filters} accountId={accountId} page={page} onPage={setPage} onDenied={setAccessError}/> : <p role="alert" className={customerCard}>Choose a valid date range. Start date must not be later than end date.</p>}</div>;
}
export default function TransactionHistory() {
  const {user,token,isAuthenticated}=useAuth(),[search]=useSearchParams();
  const raw=search.get('accountId'),accountId=raw===null?null:parseAccountId(raw);
  if(!isAuthenticated||user?.platform_role!=='customer')return null;
  if(raw!==null&&accountId===null)return <p role="alert" className={customerCard}>This record is not available to your account. Please return to My Shops. <Link to="/customer/shops">My Shops</Link></p>;
  return <HistorySession key={user.user_id+':'+token+':'+accountId} accountId={accountId}/>;
}
