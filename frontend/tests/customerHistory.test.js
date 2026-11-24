import {test} from 'node:test';
import assert from 'node:assert/strict';
import { validCalendarDate,validPeriod,historyParams,parseHistory,parseCreditStatement,createStatementDownload,saveStatementPdf } from '../src/utils/customerHistory.js';
import { fixtures } from './fixtures/customerDashboardFixtures.js';
import { statement,period } from './fixtures/customerHistoryFixtures.js';
test('inclusive calendar date validation rejects impossible dates and reversed ranges',()=>{
 for(const value of ['2026-02-30','2026-13-01','9999-12-31','invalid','0000-01-01'])assert.equal(validCalendarDate(value),false,value);
 assert.equal(validCalendarDate('2024-02-29'),true);assert.equal(validPeriod('2026-03-01','2026-02-01'),false);assert.equal(validPeriod('',''),true);assert.equal(validPeriod('','',true),false);
});
test('history parameters carry bounded filters without identity claims',()=>{
 assert.deepEqual(historyParams({business_id:'2',entry_type:'repayment',...period},8),{business_id:2,entry_type:'repayment',...period,credit_account_id:8});assert.deepEqual(historyParams({}),{});
 assert.throws(()=>historyParams({start_date:'2026-03-01',end_date:'2026-02-01'}));
});
test('history rejects responses inconsistent with active date, type, shop or account filters',()=>{
 const data={...fixtures().transactions,page_size:10};
 assert.equal(parseHistory(data,1,{},null).items.length,1);
 for(const filters of [{entry_type:'repayment'},{business_id:'3'},{start_date:'2026-12-01'},{end_date:'2026-01-01'}])assert.throws(()=>parseHistory(data,1,filters,null));
 assert.throws(()=>parseHistory(data,1,{},9));
});
test('statement validates authoritative totals and strips private metadata',()=>{
 const data=statement();data.private_note='hidden';data.transactions[0].created_by='hidden';
 const result=parseCreditStatement(data,8,period);assert.equal(result.closing_balance,'110.30');assert.equal(result.private_note,undefined);assert.equal(result.transactions[0].created_by,undefined);
 for(const patch of [{credit_account_id:9},{currency:'USD'},{closing_balance:'110.31'},{total_credit_sales:'20.11'},{start_date:'2026-01-01'},{outstanding_balance:'0.00'}])assert.throws(()=>parseCreditStatement({...statement(),...patch},8,period));
});
test('statement validates ordering, duplicate entries and complete running balances',()=>{
 for(const mutate of [d=>d.transactions.reverse(),d=>d.transactions[1].entry_id=1,d=>d.transactions[0].running_balance='999.00',d=>d.transactions[0].recorded_at='2026-01-01T00:00:00',d=>d.transactions[1].credit='0.00']){const d=statement();mutate(d);assert.throws(()=>parseCreditStatement(d,8,period));}
});
test('statement preserves huge exact balances, signed advances and complete empty periods',()=>{
 const d=statement();d.opening_balance='1999999999999.98';d.closing_balance='2000000000010.03';d.outstanding_balance=d.closing_balance;d.transactions[0].running_balance='2000000000020.08';d.transactions[1].running_balance=d.closing_balance;assert.equal(parseCreditStatement(d,8,period).closing_balance,d.closing_balance);
 const empty={...statement(),opening_balance:'-0.01',closing_balance:'-0.01',outstanding_balance:'0.00',advance_balance:'0.01',total_credit_sales:'0.00',total_repayments:'0.00',transactions:[]};assert.equal(parseCreditStatement(empty,8,period).closing_balance,'-0.01');
});
test('PDF failures are safe, retryable and authorization loss is escalated',async()=>{
 let fail=true,saved=0,denied='';const reader=createStatementDownload(async()=>{if(fail)throw {response:{status:403,data:{detail:'private'}}};return 'pdf';},()=>saved++,message=>denied=message);
 await reader.load();assert.equal(saved,0);assert.ok(denied);assert.ok(!reader.getSnapshot().error.includes('private'));fail=false;await reader.load();assert.equal(saved,1);assert.equal(reader.getSnapshot().error,'');reader.dispose();
});
test('late or superseded downloads never save former account data',async()=>{
 const pending=[],saved=[];const reader=createStatementDownload(({signal})=>new Promise(resolve=>pending.push({signal,resolve})),blob=>saved.push(blob));
 const first=reader.load(),second=reader.load();assert.equal(pending[0].signal.aborted,true);pending[1].resolve('new');await second;pending[0].resolve('old');await first;assert.deepEqual(saved,['new']);
 const third=reader.load();reader.dispose();pending[2].resolve('disposed');await third;assert.deepEqual(saved,['new']);
});
test('PDF save removes its temporary link and revokes the object URL',()=>{
 const oldDocument=globalThis.document,oldCreate=URL.createObjectURL,oldRevoke=URL.revokeObjectURL,oldTimer=globalThis.setTimeout;let clicked=false,removed=false,revoked='';const link={click(){clicked=true;},remove(){removed=true;}};
 globalThis.document={createElement:()=>link,body:{appendChild(){}}};URL.createObjectURL=()=> 'blob:test';URL.revokeObjectURL=value=>revoked=value;globalThis.setTimeout=fn=>{fn();return 1;};
 try{saveStatementPdf(new Blob(['%PDF-test']),'statement.pdf');assert.ok(clicked&&removed);assert.equal(revoked,'blob:test');assert.equal(link.download,'statement.pdf');}finally{globalThis.document=oldDocument;URL.createObjectURL=oldCreate;URL.revokeObjectURL=oldRevoke;globalThis.setTimeout=oldTimer;}
});

test('a statement PDF 404 invalidates the displayed snapshot after ownership is revoked',async()=>{
 let denied='',saved=false;const reader=createStatementDownload(async()=>{throw {response:{status:404,data:{detail:'private account'}}};},()=>saved=true,message=>denied=message);
 await reader.load();assert.equal(saved,false);assert.ok(denied.includes('not available'));assert.ok(!denied.includes('private account'));
});
