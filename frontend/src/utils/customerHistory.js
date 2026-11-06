import { parseCustomerPage, customerAccountError } from './customerAccounts.js';
export function validCalendarDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value < '0001-01-01' || value > '9999-12-30') return false;
  const stamp=new Date(value + 'T00:00:00Z');
  return !Number.isNaN(stamp.getTime()) && stamp.toISOString().slice(0, 10) === value;
}
export function validPeriod(start, end, required = false) {
  return (!required || !!start && !!end) && (!start || validCalendarDate(start)) && (!end || validCalendarDate(end)) && (!start || !end || start <= end);
}
export function historyParams(filters, accountId) {
  if (!validPeriod(filters.start_date, filters.end_date)) throw Error('Invalid period');
  return { ...(filters.business_id ? {business_id: Number(filters.business_id)} : {}),
    ...(filters.entry_type ? {entry_type: filters.entry_type} : {}),
    ...(filters.start_date ? {start_date: filters.start_date} : {}), ...(filters.end_date ? {end_date: filters.end_date} : {}),
    ...(accountId ? {credit_account_id: accountId} : {}) };
}
export function parseHistory(data, page, filters, accountId) {
  const result = parseCustomerPage('transactions', data, page, {businessId: filters.business_id ? Number(filters.business_id) : undefined, accountId: accountId || undefined});
  if (result.items.some(row => filters.entry_type && row.entry_type !== filters.entry_type || filters.start_date && row.recorded_at.slice(0,10) < filters.start_date || filters.end_date && row.recorded_at.slice(0,10) > filters.end_date)) throw Error('Mismatched filters');
  return result;
}
const money = value => typeof value === 'string' && /^-?\d+\.\d{2}$/.test(value);
const units = value => BigInt(value.replace('.', ''));
const keys = ['opening_balance','total_credit_sales','total_repayments','reversal_impact','closing_balance','outstanding_balance','advance_balance'];
export function parseCreditStatement(data, accountId, period) {
  if (data?.currency !== 'LKR' || data.credit_account_id !== accountId || !Number.isSafeInteger(data.business_id) || data.business_id <= 0 ||
    !['business_name','customer_name','time_basis','reversal_policy','historical_limitations'].every(key => typeof data[key] === 'string' && data[key].trim()) ||
    data.start_date !== period.start_date || data.end_date !== period.end_date || !validPeriod(data.start_date,data.end_date,true) ||
    !keys.every(key=>money(data[key])) || ['total_credit_sales','total_repayments','outstanding_balance','advance_balance'].some(key=>data[key].startsWith('-')) ||
    !Array.isArray(data.transactions) || data.transactions.length > 5000) throw Error('Invalid statement');
  let balance = units(data.opening_balance), sales=0n, repayments=0n, reversals=0n;
  let prior = null;const seen = new Set();
  const transactions=data.transactions.map(row=>{
    if (!Number.isSafeInteger(row.entry_id) || row.entry_id <= 0 || seen.has(row.entry_id) || !['credit_sale','repayment','reversal'].includes(row.entry_type) ||
      !['recorded','reversed','reversal'].includes(row.status) || (row.entry_type === 'reversal') !== (row.status === 'reversal') ||
      !['amount','debit','credit','running_balance'].every(key=>money(row[key])) || ['amount','debit','credit'].some(key=>row[key].startsWith('-')) ||
      typeof row.reference !== 'string' || !row.reference.trim() || typeof row.recorded_at !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(row.recorded_at) || Number.isNaN(Date.parse(row.recorded_at)) ||
      row.recorded_at.slice(0,10) < period.start_date || row.recorded_at.slice(0,10) > period.end_date ||
      prior && (row.recorded_at < prior.recorded_at || row.recorded_at === prior.recorded_at && row.entry_id <= prior.entry_id)) throw Error('Invalid statement entry');
    seen.add(row.entry_id);prior=row;
    const delta=units(row.debit)-units(row.credit);balance+=delta;
    if(balance !== units(row.running_balance)) throw Error('Invalid running balance');
    if(row.entry_type==='credit_sale') {sales+=units(row.amount);if(delta!==units(row.amount))throw Error('Invalid sale');}
    else if(row.entry_type==='repayment') {repayments+=units(row.amount);if(delta!==-units(row.amount))throw Error('Invalid repayment');}
    else reversals+=delta;
    return Object.fromEntries(['entry_id','entry_type','recorded_at','reference','amount','debit','credit','running_balance','status'].map(key=>[key,row[key]]));
  });
  if(balance!==units(data.closing_balance) || sales!==units(data.total_credit_sales) || repayments!==units(data.total_repayments) || reversals!==units(data.reversal_impact) ||
    units(data.opening_balance)+sales-repayments+reversals!==balance || units(data.outstanding_balance)!==(balance>0n?balance:0n) || units(data.advance_balance)!==(balance<0n?-balance:0n))throw Error('Statement totals mismatch');
  return {...Object.fromEntries(['currency','credit_account_id','business_id','business_name','customer_name','start_date','end_date','time_basis','reversal_policy','historical_limitations',...keys].map(key=>[key,data[key]])),transactions};
}
export function createStatementDownload(api, save, onDenied = () => {}) {
  let state={loading:false,error:''},active=true,version=0,controller;const listeners=new Set();
  const publish=next=>{state=next;if(active)listeners.forEach(fn=>fn());};
  return {getSnapshot:()=>state,subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
    async load(){active=true;controller?.abort();controller=new AbortController();const {signal}=controller,current=++version;publish({loading:true,error:''});
      try{const blob=await api({signal});if(active&&!signal.aborted&&current===version){save(blob);publish({loading:false,error:''});}}
      catch(error){if(active&&!signal.aborted&&current===version){if([401,403,404].includes(error?.response?.status))onDenied(customerAccountError(error));publish({loading:false,error:'Unable to download this statement PDF. Please retry.'});}}
    },dispose(){active=false;version++;controller?.abort();state={loading:false,error:''};}};
}
export function saveStatementPdf(blob, filename) {
  const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=filename;
  try{document.body.appendChild(link);link.click();}finally{link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
}
