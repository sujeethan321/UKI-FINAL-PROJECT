import { useEffect, useState, useSyncExternalStore } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import { useCustomerRead } from '../../hooks/useCustomerRead';
import { getCreditStatement, getCreditStatementPdf } from '../../services/customerDashboardService';
import { parseAccountId } from '../../utils/customerAccounts';
import { validPeriod, parseCreditStatement, createStatementDownload, saveStatementPdf } from '../../utils/customerHistory';
import { formatCustomerMoney, formatRecordedTime } from '../../utils/customerDashboard';
import { CustomerDataState, customerButton, customerCard } from '../../components/customer/CustomerData';

export function StatementContent({data}) {
 return <article className={customerCard}><h3 className="break-words text-xl font-bold">{data.business_name}</h3><p className="mt-2 break-words">Customer: {data.customer_name}</p><p className="mt-2 text-sm">Account #{data.credit_account_id} · {data.start_date} to {data.end_date} (inclusive)</p><dl className="mt-5 grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-3">{[['Opening balance','opening_balance'],['Credit sales','total_credit_sales'],['Repayment records','total_repayments'],['Reversal impact','reversal_impact'],['Closing balance','closing_balance']].map(([label,key])=><div key={key} className="min-w-0 rounded-lg bg-[#F5F8FC] p-4"><dt className="text-sm">{label}</dt><dd className="mt-2 break-words font-bold [overflow-wrap:anywhere]">{formatCustomerMoney(data[key])}</dd></div>)}</dl><p className="mt-4 text-xs text-[#64748B]">Opening + credit sales − repayments + reversal impact = closing balance.</p><h4 className="mt-6 font-bold">Statement entries</h4><ul className="divide-y divide-[#D4E2EE]">{data.transactions.map(row=><li key={row.entry_id} className="grid min-w-0 gap-3 py-4 sm:grid-cols-2"><div className="min-w-0"><p className="font-semibold">{{credit_sale:'Credit sale',repayment:'Repayment record',reversal:'Reversal'}[row.entry_type]} · {row.status}</p><p className="break-all text-sm">{row.reference}</p><time className="text-xs text-[#64748B]" dateTime={row.recorded_at}>{formatRecordedTime(row.recorded_at)}</time></div><div className="min-w-0 break-words text-sm [overflow-wrap:anywhere]"><p>Debit: {formatCustomerMoney(row.debit)}</p><p>Credit: {formatCustomerMoney(row.credit)}</p><p className="font-semibold">Running balance: {formatCustomerMoney(row.running_balance)}</p></div></li>)}</ul>{!data.transactions.length && <p className="py-5 text-sm">No activity in this period.</p>}{['reversal_policy','time_basis','historical_limitations'].map(key=><p key={key} className="mt-3 text-xs text-[#64748B]">{data[key]}</p>)}<p className="mt-3 text-xs text-[#64748B]">Repayment records do not independently verify bank or card settlement.</p></article>;
}
export function StatementDownloadView({state,onDownload}) {
 return <div className="space-y-3"><button type="button" className={customerButton} disabled={state.loading} onClick={onDownload}>{state.loading?'Generating PDF…':'Download PDF'}</button>{state.loading && <p role="status">Preparing your authorized statement PDF...</p>}{state.error && <p role="alert" className="border-l-4 border-[#DC4545] pl-3 text-sm">{state.error}</p>}<p className="text-xs text-[#64748B]">The PDF is freshly generated from server records and may reflect activity committed since this view loaded.</p></div>;
}
function Download({accountId,period,onDenied}) {
 const [reader]=useState(()=>createStatementDownload(options=>getCreditStatementPdf(accountId,period,options),blob=>saveStatementPdf(blob,'LankaPex-statement-'+accountId+'-'+period.start_date+'-'+period.end_date+'.pdf'),onDenied));
 const state=useSyncExternalStore(reader.subscribe,reader.getSnapshot,reader.getSnapshot);
 useEffect(()=>()=>reader.dispose(),[reader]);
 return <StatementDownloadView state={state} onDownload={reader.load}/>;
}
function StatementResult({accountId,period,onDenied}) {
 const [state,reader]=useCustomerRead(options=>getCreditStatement(accountId,period,options),data=>parseCreditStatement(data,accountId,period),onDenied);
 return <CustomerDataState state={state} retry={reader.load} label="credit statement">{state.data && <div className="space-y-5"><Download accountId={accountId} period={period} onDenied={onDenied}/><StatementContent data={state.data}/></div>}</CustomerDataState>;
}
function StatementSession({accountId}) {
 const [start,setStart]=useState(''),[end,setEnd]=useState(''),[period,setPeriod]=useState(null),[accessError,setAccessError]=useState('');
 const valid=validPeriod(start,end,true);
 if(accessError)return <div className="space-y-4"><Link className={customerButton} to="/customer/shops">Back to My Shops</Link><p role="alert" className={customerCard}>{accessError}</p></div>;
 return <div className="space-y-6"><Link className={customerButton} to={'/customer/credit/'+accountId}>Back to account details</Link><h2 className="text-2xl font-bold">Credit Statement</h2><form className={customerCard} onSubmit={e=>{e.preventDefault();if(valid)setPeriod({start_date:start,end_date:end});}}><div className="grid gap-4 sm:grid-cols-2">{[['Start date',start,setStart],['End date',end,setEnd]].map(([label,value,set])=><label className="text-sm" key={label}>{label}<input required type="date" className="mt-2 block w-full rounded-lg border border-[#D4E2EE] p-2" value={value} onChange={e=>{set(e.target.value);setPeriod(null);}}/></label>)}</div>{!valid && (start||end) && <p role="alert" className="mt-3 text-sm">Choose both dates, with start date no later than end date.</p>}<button type="submit" className={customerButton+' mt-4'} disabled={!valid}>View Statement</button><p className="mt-3 text-xs text-[#64748B]">Inclusive calendar dates in the database recorded clock. Large accounts above 5,000 ledger entries need assistance from the shop.</p></form>{period && <StatementResult key={JSON.stringify(period)} accountId={accountId} period={period} onDenied={setAccessError}/>}</div>;
}
export default function CreditStatement() {
 const {accountId:raw}=useParams(),{user,token,isAuthenticated}=useAuth(),accountId=parseAccountId(raw);
 if(!isAuthenticated||user?.platform_role!=='customer')return null;
 if(accountId===null)return <p role="alert" className={customerCard}>This record is not available to your account. Please return to My Shops. <Link to="/customer/shops">My Shops</Link></p>;
 return <StatementSession key={user.user_id+':'+token+':'+accountId} accountId={accountId}/>;
}
