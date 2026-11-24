// Purpose: Render the credit statement screen and connect its user interactions to shared application state and services.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useEffect, useState, useSyncExternalStore } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import { useCustomerRead } from '../../hooks/useCustomerRead';
import { getCreditStatement, getCreditStatementPdf } from '../../services/customerDashboardService';
import { parseAccountId } from '../../utils/customerAccounts';
import { validPeriod, parseCreditStatement, createStatementDownload, saveStatementPdf } from '../../utils/customerHistory';
import { formatCustomerMoney, formatRecordedTime } from '../../utils/customerDashboard';
import { CustomerDataState, customerButton, customerCard } from '../../components/customer/CustomerData';

// Render the statement content interface and connect its controls to the state and callbacks defined here.
export function StatementContent({data}) {
  const { tr } = useAppTranslation();
 return <article className={customerCard}><h3 className="break-words text-xl font-bold">{data.business_name}</h3><p className="mt-2 break-words">{tr("Customer:")} {data.customer_name}</p><p className="mt-2 text-sm">{tr("Account #")}{data.credit_account_id} · {data.start_date} {tr("to")} {data.end_date} {tr("(inclusive)")}</p><dl className="mt-5 grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-3">{[['Opening balance','opening_balance'],['Credit sales','total_credit_sales'],['Repayment records','total_repayments'],['Reversal impact','reversal_impact'],['Closing balance','closing_balance']].map(([label,key])=><div key={key} className="min-w-0 rounded-lg bg-[#F5F8FC] p-4"><dt className="text-sm">{tr(label)}</dt><dd className="mt-2 break-words font-bold [overflow-wrap:anywhere]">{formatCustomerMoney(data[key])}</dd></div>)}</dl><p className="mt-4 text-xs text-[#64748B]">{tr("Opening + credit sales − repayments + reversal impact = closing balance.")}</p><h4 className="mt-6 font-bold">{tr("Statement entries")}</h4><ul className="divide-y divide-[#D4E2EE]">{data.transactions.map(row=><li key={row.entry_id} className="grid min-w-0 gap-3 py-4 sm:grid-cols-2"><div className="min-w-0"><p className="font-semibold">{tr({credit_sale:'Credit sale',repayment:'Repayment record',reversal:'Reversal'}[row.entry_type])} · {tr(row.status)}</p><p className="break-all text-sm">{row.reference}</p><time className="text-xs text-[#64748B]" dateTime={row.recorded_at}>{formatRecordedTime(row.recorded_at)}</time></div><div className="min-w-0 break-words text-sm [overflow-wrap:anywhere]"><p>{tr("Debit:")} {formatCustomerMoney(row.debit)}</p><p>{tr("Credit:")} {formatCustomerMoney(row.credit)}</p><p className="font-semibold">{tr("Running balance:")} {formatCustomerMoney(row.running_balance)}</p></div></li>)}</ul>{!data.transactions.length && <p className="py-5 text-sm">{tr("No activity in this period.")}</p>}{['reversal_policy','time_basis','historical_limitations'].map(key=><p key={key} className="mt-3 text-xs text-[#64748B]">{data[key]}</p>)}<p className="mt-3 text-xs text-[#64748B]">{tr("Repayment records do not independently verify bank or card settlement.")}</p></article>;
}
// Render the statement download view interface and connect its controls to the state and callbacks defined here.
export function StatementDownloadView({state,onDownload}) {
  const { tr } = useAppTranslation();
 return <div className="space-y-3"><button type="button" className={customerButton} disabled={state.loading} onClick={onDownload}>{state.loading?tr("Generating PDF…"):tr("Download PDF")}</button>{state.loading && <p role="status">{tr("Preparing your authorized statement PDF...")}</p>}{state.error && <p role="alert" className="border-l-4 border-[#DC4545] pl-3 text-sm">{tr(state.error)}</p>}<p className="text-xs text-[#64748B]">{tr("The PDF is freshly generated from server records and may reflect activity committed since this view loaded.")}</p></div>;
}
// Render the download interface and connect its controls to the state and callbacks defined here.
function Download({accountId,period,onDenied}) {
 const [reader]=useState(()=>createStatementDownload(options=>getCreditStatementPdf(accountId,period,options),blob=>saveStatementPdf(blob,'LankaPex-statement-'+accountId+'-'+period.start_date+'-'+period.end_date+'.pdf'),onDenied));
 const state=useSyncExternalStore(reader.subscribe,reader.getSnapshot,reader.getSnapshot);
 // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
 useEffect(()=>()=>reader.dispose(),[reader]);
 return <StatementDownloadView state={state} onDownload={reader.load}/>;
}
// Render the statement result interface and connect its controls to the state and callbacks defined here.
function StatementResult({accountId,period,onDenied}) {
  const { tr } = useAppTranslation();
 const [state,reader]=useCustomerRead(options=>getCreditStatement(accountId,period,options),data=>parseCreditStatement(data,accountId,period),onDenied);
 return <CustomerDataState state={state} retry={reader.load} label={tr("credit statement")}>{state.data && <div className="space-y-5"><Download accountId={accountId} period={period} onDenied={onDenied}/><StatementContent data={state.data}/></div>}</CustomerDataState>;
}
// Render the statement session interface and connect its controls to the state and callbacks defined here.
function StatementSession({accountId}) {
  const { tr } = useAppTranslation();
 const [start,setStart]=useState(''),[end,setEnd]=useState(''),[period,setPeriod]=useState(null),[accessError,setAccessError]=useState('');
 const valid=validPeriod(start,end,true);
 if(accessError)return <div className="space-y-4"><Link className={customerButton} to="/customer/shops">{tr("Back to My Shops")}</Link><p role="alert" className={customerCard}>{tr(accessError)}</p></div>;
 return <div className="space-y-6"><Link className={customerButton} to={'/customer/credit/'+accountId}>{tr("Back to account details")}</Link><h2 className="text-2xl font-bold">{tr("Credit Statement")}</h2><form className={customerCard} onSubmit={e=>{e.preventDefault();if(valid)setPeriod({start_date:start,end_date:end});}}><div className="grid gap-4 sm:grid-cols-2">{[['Start date',start,setStart],['End date',end,setEnd]].map(([label,value,set])=><label className="text-sm" key={label}>{tr(label)}<input required type="date" className="mt-2 block w-full rounded-lg border border-[#D4E2EE] p-2" value={value} onChange={e=>{set(e.target.value);setPeriod(null);}}/></label>)}</div>{!valid && (start||end) && <p role="alert" className="mt-3 text-sm">{tr("Choose both dates, with start date no later than end date.")}</p>}<button type="submit" className={customerButton+' mt-4'} disabled={!valid}>{tr("View Statement")}</button><p className="mt-3 text-xs text-[#64748B]">{tr("Inclusive calendar dates in the database recorded clock. Large accounts above 5,000 ledger entries need assistance from the shop.")}</p></form>{period && <StatementResult key={JSON.stringify(period)} accountId={accountId} period={period} onDenied={setAccessError}/>}</div>;
}
// Render the credit statement interface and connect its controls to the state and callbacks defined here.
export default function CreditStatement() {
  const { tr } = useAppTranslation();
 const {accountId:raw}=useParams(),{user,token,isAuthenticated}=useAuth(),accountId=parseAccountId(raw);
 if(!isAuthenticated||user?.platform_role!=='customer')return null;
 if(accountId===null)return <p role="alert" className={customerCard}>{tr("This record is not available to your account. Please return to My Shops.")} <Link to="/customer/shops">{tr("My Shops")}</Link></p>;
 return <StatementSession key={user.user_id+':'+token+':'+accountId} accountId={accountId}/>;
}
