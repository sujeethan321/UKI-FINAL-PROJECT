import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import {createServer} from 'vite';
import {transaction} from './fixtures/customerDashboardFixtures.js';
import {statement,period} from './fixtures/customerHistoryFixtures.js';
const ready=data=>({data,loading:false,error:'',status:null});
test('customer history and statement React views and authenticated service contracts',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
 const {default:History,TransactionRows,HistoryFilters}=await server.ssrLoadModule('/src/pages/customer/TransactionHistory.jsx');
 const {default:Statement,StatementContent,StatementDownloadView}=await server.ssrLoadModule('/src/pages/customer/CreditStatement.jsx');
 const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx');const {default:Guard}=await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
 const render=(component,props)=>renderToStaticMarkup(h(MemoryRouter,null,h(component,props)));
 await t.test('authorized sale and repayment cards expose only returned detail fields',()=>{
 const html=render(TransactionRows,{state:ready({total:2,items:[transaction(),transaction({entry_id:42,entry_type:'repayment',reference:'RP-test',balance_delta:'-100.25'})]}),page:1,onPage(){}});
 for(const value of ['Credit sale','Repayment record','Linked Shop','CS-test-reference','RP-test','View transaction details','Account #8','href="/customer/credit/8/statement"','LKR -100.25'])assert.ok(html.includes(value),value);
 assert.ok(!html.includes('Make Payment'));
 });
 await t.test('filters render linked-shop selection, supported types and inclusive date controls',()=>{
 const html=render(HistoryFilters,{filters:{business_id:'2',entry_type:'repayment',...period},shopLabel:'Linked Shop',onChange(){},onAllShops(){}});
 for(const value of ['Shop: Linked Shop','All linked shops','value="credit_sale"','value="repayment" selected','Start date','End date','without timezone conversion','do not independently verify'])assert.ok(html.includes(value),value);
 });
 await t.test('empty, loading and network errors never fabricate history',()=>{
 assert.ok(render(TransactionRows,{state:ready({total:0,items:[]}),page:1,onPage(){}}).includes('No transactions match these filters'));
 const loading=render(TransactionRows,{state:{data:null,loading:true,error:''},page:1,onPage(){}});assert.ok(loading.includes('role="status"'));assert.ok(!loading.includes('LKR 0.00'));
 const error=render(TransactionRows,{state:{data:null,loading:false,error:'Check your connection',status:null},retry(){},page:1,onPage(){}});assert.ok(error.includes('Retry transactions'));assert.ok(error.includes('role="alert"'));
 });
 await t.test('statement shows full authoritative snapshot and calculation definitions',()=>{
 const html=render(StatementContent,{data:statement()});
 for(const value of ['Linked Shop','Customer: Kumar','2026-02-01 to 2026-02-28','Opening balance','LKR 100.25','LKR 110.30','Repayment record','Reversal impact','Running balance','RP-two','Reconstructed from stored records'])assert.ok(html.includes(value),value);
 const d=statement();d.transactions=[];assert.ok(render(StatementContent,{data:d}).includes('No activity in this period.'));
 });
 await t.test('real PDF download action handles slow responses and safe failure',()=>{
 assert.ok(render(StatementDownloadView,{state:{loading:false,error:''},onDownload(){}}).includes('Download PDF'));
 const busy=render(StatementDownloadView,{state:{loading:true,error:''},onDownload(){}});assert.ok(busy.includes('disabled'));assert.ok(busy.includes('role="status"'));
 assert.ok(render(StatementDownloadView,{state:{loading:false,error:'Unable to download this statement PDF. Please retry.'},onDownload(){}}).includes('role="alert"'));
 });
 await t.test('direct routes require Customer role and invalid account identifiers fail safely',()=>{
 const auth={isAuthenticated:true,loading:false,token:'fixture',user:{user_id:1,platform_role:'customer',account_status:'active'}};
 const route=(value,path)=>renderToStaticMarkup(h(MemoryRouter,{initialEntries:[path]},h(AuthContext.Provider,{value},h(Routes,null,h(Route,{element:h(Guard,{allowedRoles:['customer']})},h(Route,{path:'/customer/transactions',element:h(History)}),h(Route,{path:'/customer/credit/:accountId/statement',element:h(Statement)}))))));
 assert.ok(route(auth,'/customer/transactions').includes('Transaction History'));assert.ok(route(auth,'/customer/credit/8/statement').includes('Credit Statement'));
 for(const path of ['/customer/transactions?accountId=-1','/customer/credit/invalid/statement'])assert.ok(route(auth,path).includes('This record is not available'));
 for(const role of ['shop_owner','driver','admin'])assert.ok(!route({...auth,user:{...auth.user,platform_role:role}},'/customer/transactions').includes('Transaction History'));
 assert.ok(!route({...auth,isAuthenticated:false},'/customer/credit/8/statement').includes('View Statement'));
 });
 await t.test('history filters and statements use authenticated scoped GETs; PDF verifies type and signature',async()=>{
 const {default:api}=await server.ssrLoadModule('/src/services/api.js');const service=await server.ssrLoadModule('/src/services/customerDashboardService.js');const previous=api.defaults.adapter,storage=globalThis.localStorage,calls=[];let bad=false;globalThis.localStorage={getItem:()=> 'fixture'};
 api.defaults.adapter=async config=>{calls.push(config);return {data:config.responseType==='blob'?new Blob([bad?'not pdf':'%PDF-test']):{},status:200,statusText:'OK',headers:{'content-type':'application/pdf'},config};};
 try{const signal=new AbortController().signal;await service.getTransactionHistory({business_id:2,entry_type:'repayment',...period},2,{signal});await service.getCreditStatement(8,period,{signal});await service.getCreditStatementPdf(8,period,{signal});
 assert.deepEqual(calls.map(c=>c.url),['/customer/transactions','/customer/credit-accounts/8/statement','/customer/credit-accounts/8/statement.pdf']);assert.deepEqual(calls[0].params,{business_id:2,entry_type:'repayment',...period,page:2,page_size:10});assert.deepEqual(calls[1].params,period);assert.equal(calls[2].responseType,'blob');for(const call of calls){assert.equal(call.headers.Authorization,'Bearer fixture');assert.equal(call.signal,signal);assert.equal(call.method,'get');}bad=true;await assert.rejects(service.getCreditStatementPdf(8,period,{signal}));
 }finally{api.defaults.adapter=previous;if(storage===undefined)delete globalThis.localStorage;else globalThis.localStorage=storage;}
 });
 await t.test('navigation targets real routes; request components remount on filters, dates and session',async()=>{
 const app=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');for(const value of ['path="transactions" element={<TransactionHistory />}','path="credit/:accountId/statement" element={<CreditStatement />}'])assert.ok(app.includes(value));
 const sidebar=await readFile(new URL('../src/components/customer/CustomerSidebar.jsx',import.meta.url),'utf8');assert.ok(sidebar.includes('to="/customer/transactions"'));
 const source=await readFile(new URL('../src/pages/customer/TransactionHistory.jsx',import.meta.url),'utf8');for(const value of ['key={JSON.stringify([filters,accountId,page])}','setPage(1)','sm:grid-cols-','overflow-wrap:anywhere'])assert.ok(source.includes(value));
 const statementSource=await readFile(new URL('../src/pages/customer/CreditStatement.jsx',import.meta.url),'utf8');assert.ok(statementSource.includes('setPeriod(null)'));assert.ok(statementSource.includes('key={JSON.stringify(period)}'));assert.ok(!statementSource.includes('localStorage'));
 });
 }finally{await server.close();}
});
