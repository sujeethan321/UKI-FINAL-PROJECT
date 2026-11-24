import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseAccountId, parseAccountDetail, parseCustomerPage, createCustomerRead, customerAccountError } from '../src/utils/customerAccounts.js';
import { fixtures, transaction } from './fixtures/customerDashboardFixtures.js';
const account = () => fixtures().accounts.credit_accounts[0];
test('account IDs reject ambiguous or unsafe route values', () => {
 assert.equal(parseAccountId('8'),8);
 for(const id of ['0','-1','1.5','1e2','08','9007199254740992',undefined]) assert.equal(parseAccountId(id),null);
});
test('account detail validates identity, exact money and projects private fields away', () => {
 const data={currency:'LKR',account:{...account(),credit_limit:'1999999999999.98',private_note:'secret'}};
 assert.equal(parseAccountDetail(data,8).credit_limit,'1999999999999.98');
 assert.equal(parseAccountDetail(data,8).private_note,undefined);
 assert.throws(()=>parseAccountDetail(data,9)); assert.throws(()=>parseAccountDetail({...data,currency:'USD'},8));
});
test('paginated responses validate complete pages and account/shop scope', () => {
 const data={...fixtures().accounts,page:2,page_size:10,total:21,credit_accounts:Array.from({length:10},(_,i)=>({...account(),credit_account_id:i+1}))};
 assert.equal(parseCustomerPage('accounts',data,2,{businessId:2}).items.length,10);
 assert.throws(()=>parseCustomerPage('accounts',data,1));
 assert.throws(()=>parseCustomerPage('accounts',data,2,{businessId:3}));
 data.credit_accounts[9].credit_account_id=1; assert.throws(()=>parseCustomerPage('accounts',data,2));
 const tx={...fixtures().transactions,page_size:10,transactions:[transaction()]};
 assert.throws(()=>parseCustomerPage('transactions',tx,1,{accountId:9}));
 assert.throws(()=>parseCustomerPage('transactions',tx,1,{businessId:3}));
 assert.equal(parseCustomerPage('transactions',tx,1,{accountId:8,businessId:2}).items.length,1);
});
test('missing and foreign accounts share a safe unavailable message',()=>{
 assert.equal(customerAccountError({response:{status:404,data:{detail:'private'}}}),customerAccountError({response:{status:422}}));
 assert.ok(!customerAccountError({response:{status:404,data:{detail:'private'}}}).includes('private'));
});
test('reader aborts replaced requests, ignores late results and clears data on dispose',async()=>{
 const requests=[];const reader=createCustomerRead(({signal})=>new Promise(resolve=>requests.push({resolve,signal})),x=>x);
 const first=reader.load(),second=reader.load(); assert.equal(requests[0].signal.aborted,true);
 requests[1].resolve('new');await second; requests[0].resolve('old');await first;
 assert.equal(reader.getSnapshot().data,'new');reader.dispose();assert.equal(reader.getSnapshot().data,null);
});
test('reader denies expired/forbidden access and never retains financial data on errors',async()=>{
 for(const status of [401,403,404,409,500]){
 let fail=false,denied='';const reader=createCustomerRead(async()=>{if(fail)throw {response:{status,data:{detail:'secret'}}};return 'balance';},x=>x,x=>denied=x);
 await reader.load();assert.equal(reader.getSnapshot().data,'balance');fail=true;await reader.load();
 assert.equal(reader.getSnapshot().data,null);assert.equal(reader.getSnapshot().status,status);
 assert.equal(Boolean(denied),[401,403].includes(status));assert.ok(!reader.getSnapshot().error.includes('secret'));
 }
});
test('reader rejects malformed data and disposed responses without publishing',async()=>{
 const reader=createCustomerRead(async()=>({}),()=>{throw Error('private');});await reader.load();assert.equal(reader.getSnapshot().data,null);assert.ok(reader.getSnapshot().error);
 let resolve;const disposed=createCustomerRead(()=>new Promise(r=>resolve=r),x=>x);const pending=disposed.load();disposed.dispose();resolve('late');await pending;assert.equal(disposed.getSnapshot().data,null);
});

test('network failures remain retryable without fabricating an empty account',async()=>{
 let failed=true;const reader=createCustomerRead(async()=>{if(failed)throw Error('private diagnostics');return 'restored';},x=>x);
 await reader.load();assert.equal(reader.getSnapshot().data,null);assert.ok(reader.getSnapshot().error);assert.ok(!reader.getSnapshot().error.includes('private'));failed=false;await reader.load();assert.equal(reader.getSnapshot().data,'restored');
});
