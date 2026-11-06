import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { createServer } from 'vite';
import { fixtures, transaction } from './fixtures/customerDashboardFixtures.js';
const ready=data=>({data,loading:false,error:'',status:null});
test('My Shops and credit details use real customer data and protected routes',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
 const {MyShopsView,ShopAccountChoices,default:Shops}=await server.ssrLoadModule('/src/pages/customer/MyShops.jsx');
 const {AccountDetailsView,AccountActivityView,default:Details}=await server.ssrLoadModule('/src/pages/customer/CreditAccountDetails.jsx');
 const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx');
 const {default:Guard}=await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
 const render=(component,props)=>renderToStaticMarkup(h(MemoryRouter,null,h(component,props)));
 const noop=()=>{};const f=fixtures();const account=f.accounts.credit_accounts[0];
 await t.test('shop summary uses backend totals independently from the current page',()=>{
 const html=render(MyShopsView,{summary:ready({...f.summary,linked_shop_count:24,total_outstanding_balance:'1999999999999.98'}),shops:ready({total:24,items:f.shops.shops}),page:2,onPage:noop});
 for(const value of ['24','LKR 1,999,999,999,999.98','Linked Shop','View Details','aria-expanded="false"','Page 2'])assert.ok(html.includes(value),value);
 });
 await t.test('multiple accounts require explicit selection with distinct links',()=>{
 const html=render(ShopAccountChoices,{state:ready({total:2,items:[account,{...account,credit_account_id:9,account_status:'suspended'}]}),page:1,onPage:noop});
 for(const value of ['Choose the credit account','href="/customer/credit/8"','href="/customer/credit/9"','suspended'])assert.ok(html.includes(value),value);
 });
 await t.test('account detail displays authoritative limit, balance, allowance and safe back navigation',()=>{
 const html=render(AccountDetailsView,{state:ready({...account,credit_limit:'1000.00',outstanding_balance:'0.00',available_credit:'777.12',account_status:'closed'})});
 for(const value of ['href="/customer/shops"','Account #8','closed','LKR 0.00','LKR 1,000.00','LKR 777.12'])assert.ok(html.includes(value),value);
 assert.ok(!html.includes('Make Payment'));
 });
 await t.test('empty, loading and unavailable states never invent balances',()=>{
 const html=render(AccountDetailsView,{state:{data:null,loading:true,error:''}});assert.ok(html.includes('Loading'));assert.ok(!html.includes('LKR 0.00'));
 const failed=render(AccountDetailsView,{state:{data:null,loading:false,error:'Record unavailable',status:404}});assert.ok(failed.includes('Record unavailable'));assert.ok(!failed.includes('Retry'));
 const empty=render(MyShopsView,{summary:ready({...f.summary,linked_shop_count:0,total_outstanding_balance:'0.00'}),shops:ready({total:0,items:[]}),page:1,onPage:noop});assert.ok(empty.includes('No shops are linked'));
 const noAccount=render(MyShopsView,{summary:ready(f.summary),shops:ready({total:1,items:[{...f.shops.shops[0],credit_account_count:0}]}),page:1,onPage:noop});assert.ok(noAccount.includes('No credit account at this shop yet.'));assert.ok(!noAccount.includes('View Details'));
 });
 await t.test('history preserves repayments, reversals and empty results',()=>{
 const html=render(AccountActivityView,{state:ready({total:2,items:[transaction({entry_type:'repayment'}),transaction({entry_id:42,entry_type:'reversal',status:'reversal',balance_delta:'-100.25'})]}),page:1,onPage:noop});
 for(const value of ['Repayment record','Reversal','LKR -100.25','do not independently verify bank or card settlement'])assert.ok(html.includes(value),value);
 assert.ok(render(AccountActivityView,{state:ready({total:0,items:[]}),page:1,onPage:noop}).includes('No transactions for this account yet.'));
 });
 await t.test('direct customer routes enforce role and invalid IDs display generic fallback',()=>{
 const auth={isAuthenticated:true,loading:false,token:'fixture',user:{user_id:1,platform_role:'customer',account_status:'active'}};
 const route=(value,path)=>renderToStaticMarkup(h(MemoryRouter,{initialEntries:[path]},h(AuthContext.Provider,{value},h(Routes,null,h(Route,{element:h(Guard,{allowedRoles:['customer']})},h(Route,{path:'/customer/shops',element:h(Shops)}),h(Route,{path:'/customer/credit/:accountId',element:h(Details)}))))));
 assert.ok(route(auth,'/customer/shops').includes('My Shops'));assert.ok(route(auth,'/customer/credit/8').includes('Credit Account Details'));
 assert.ok(route(auth,'/customer/credit/invalid').includes('This record is not available'));
 for(const role of ['shop_owner','driver','admin'])assert.ok(!route({...auth,user:{...auth.user,platform_role:role}},'/customer/credit/8').includes('Credit Account Details'));
 assert.ok(!route({...auth,isAuthenticated:false},'/customer/shops').includes('Total Linked Shops'));
 });
 await t.test('mobile layouts wrap financial values and preserve responsive grids',async()=>{
 const shops=await readFile(new URL('../src/pages/customer/MyShops.jsx',import.meta.url),'utf8');const details=await readFile(new URL('../src/pages/customer/CreditAccountDetails.jsx',import.meta.url),'utf8');
 for(const source of [shops,details])for(const cls of ['min-w-0','sm:grid-cols-2','overflow-wrap:anywhere'])assert.ok(source.includes(cls),cls);
 });
 await t.test('shared authenticated API uses exact IDs, filters, pagination and cancellation',async()=>{
 const {default:api}=await server.ssrLoadModule('/src/services/api.js');const service=await server.ssrLoadModule('/src/services/customerDashboardService.js');
 const previous=api.defaults.adapter,storage=globalThis.sessionStorage,calls=[];globalThis.sessionStorage={getItem:()=> 'fixture'};
 api.defaults.adapter=async config=>{calls.push(config);return {data:{},status:200,statusText:'OK',headers:{},config};};
 try{const signal=new AbortController().signal;await service.getMyShops(2,{signal});await service.getShopCreditAccounts(2,3,{signal});await service.getCustomerAccountDetail(8,{signal});await service.getAccountTransactions(8,2,{signal});
 assert.deepEqual(calls.map(c=>c.url),['/customer/shops','/customer/credit-accounts','/customer/credit-accounts/8','/customer/transactions']);
 assert.deepEqual(calls[0].params,{page:2,page_size:10});assert.deepEqual(calls[1].params,{business_id:2,page:3,page_size:10});assert.deepEqual(calls[3].params,{credit_account_id:8,page:2,page_size:10});
 for(const c of calls){assert.equal(c.method,'get');assert.equal(c.signal,signal);assert.equal(c.headers.Authorization,'Bearer fixture');}
 }finally{api.defaults.adapter=previous;if(storage===undefined)delete globalThis.sessionStorage;else globalThis.sessionStorage=storage;}
 });
 }finally{await server.close();}
});
