import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
import {createServer} from 'vite';
import {parseCustomerOrdersPage} from '../src/utils/customerOrders.js';

const order=(patch={})=>({order_id:7,reference:'SYNTHETIC-ORDER',business_id:2,business_name:'Synthetic Shop',status:'submitted',payment_method:'cash',payment_status:'unpaid',total:'12.50',subtotal:'12.50',currency:'LKR',created_at:'2026-11-08T10:00:00',updated_at:'2026-11-08T10:00:00',credit_sale_id:null,items:[{product_id:3,product_name:'Synthetic Item',quantity:1,unit_price:'12.50',line_total:'12.50'}],...patch});
const page=orders=>({page:1,page_size:10,total:orders.length,orders});
const section=data=>({data,loading:false,error:''});

test('new Customer order projections reject malformed/duplicate rows and discard private extras',()=>{
  const result=parseCustomerOrdersPage(page([order({private_email:'PRIVATE'})]));
  assert.equal(result.orders[0].total,'12.50');assert.ok(!JSON.stringify(result).includes('PRIVATE'));
  for(const data of [page([order(),order()]),page([order({status:'delivered'})]),page([order({total:12.5})]),page([order({items:[]})]),{...page([]),page:2}])assert.throws(()=>parseCustomerOrdersPage(data));
});

test('Customer restoration views, real API boundaries and retained behavior',async t=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try {
    const load=path=>server.ssrLoadModule('/src/'+path);
    const render=(View,props)=>renderToStaticMarkup(h(MemoryRouter,null,h(View,props)));
    await t.test('sidebar retains routes without the removed identity footer',async()=>{
      const {default:View}=await load('components/customer/CustomerSidebar.jsx');
      const html=render(View,{user:{full_name:'Synthetic Customer'}});
      for(const path of ['dashboard','shops/explore','orders','cart','shops','credit-accounts','transactions','deliveries','notifications','profile','settings'])assert.ok(html.includes('href="/customer/'+path+'"'),path);
      assert.doesNotMatch(html,/Synthetic Customer|Kavindu Silva|Planned/);
    });
    await t.test('financial trio uses authoritative summary and never infers overdue totals',async()=>{
      const {default:View}=await load('components/customer/CustomerCreditOverview.jsx');
      const html=render(View,{summary:{total_outstanding_balance:'9876.54',linked_shop_count:4}});
      assert.equal((html.match(/<article/g)||[]).length,3);assert.match(html,/LKR 9,876.54/);assert.match(html,/Due-date totals unavailable/);assert.match(html,/Overdue totals unavailable/);assert.doesNotMatch(html,/28 Oct|LKR 8,000/);
      assert.doesNotMatch(render(View,{summary:null,loading:true}),/LKR 0.00/);
    });
    await t.test('credit accounts retain statement navigation and do not derive balances from history',async()=>{
      const {CustomerCreditAccountsView:View}=await load('pages/customer/CustomerCreditAccounts.jsx');
      const html=render(View,{summary:section({total_outstanding_balance:'9876.54',linked_shop_count:1}),accounts:section({total:1,items:[{credit_account_id:18,business_name:'Synthetic Shop',outstanding_balance:'9876.54',account_status:'active'}]}),transactions:section({items:[]}),selected:18,page:1});
      assert.match(html,/LKR 9,876.54/);assert.match(html,/href="\/customer\/credit\/18\/statement"/);assert.match(html,/Due date unavailable/);assert.match(html,/No transactions to display yet/);
    });
    await t.test('delivery view reports bounded order pagination, actual states and absent operational data',async()=>{
      const {CustomerDeliveriesView:View}=await load('pages/customer/CustomerDeliveries.jsx');
      const html=render(View,{state:section({orderTotal:24,records:[{order:order(),delivery:{reference:'DEL-SYNTHETIC',status:'assigned'}}]}),page:1,filter:'',query:'',selected:null});
      assert.match(html,/Synthetic Shop/);assert.match(html,/Driver assigned/);assert.match(html,/Pagination counts orders/);assert.match(html,/No|not available/);assert.doesNotMatch(html,/5 km|4.8|Estimated Delivery/);
    });
    await t.test('profile renders only authenticated identity without false verification or saved addresses',async()=>{
      const {CustomerProfileView:View}=await load('pages/customer/CustomerProfile.jsx');
      const html=render(View,{user:{user_id:4,full_name:'Synthetic Customer',email:'synthetic@example.invalid',account_status:'active',is_verified:true}});
      assert.match(html,/Synthetic Customer/);assert.match(html,/synthetic@example.invalid/);assert.match(html,/Delivery Addresses/);assert.doesNotMatch(html,/>Verified<|Kavindu|Home<|15 Jan/);
    });
    await t.test('settings have working destinations and logout without pretend persistence switches',async()=>{
      const {CustomerSettingsView:View}=await load('pages/customer/CustomerSettings.jsx');
      const html=render(View,{});for(const title of ['Notifications','Application Preferences','Privacy','Security &amp; Account','Sign Out'])assert.ok(html.includes(title),title);
      assert.match(html,/href="\/customer\/notifications"/);assert.doesNotMatch(html,/type="checkbox"|Save Preferences|3 enabled/);
    });
    await t.test('Customer inbox conceals prior rows/count on auth failure',async()=>{
      const {CustomerInboxView:View}=await load('components/customer/CustomerInbox.jsx');
      const html=render(View,{state:{authError:'Session expired',count:72,typeFilter:'',readFilter:'all',list:{total:1,notifications:[{title:'PRIVATE-OLD-DATA'}]}},actions:{}});
      assert.match(html,/Session expired/);assert.doesNotMatch(html,/PRIVATE-OLD-DATA|72 unread/);
    });
    await t.test('header catalogue query initializes actual bounded shop search',async()=>{
      const {createCustomerCatalogueWorkflow}=await load('utils/customerCatalogue.js');const calls=[];
      const workflow=createCustomerCatalogueWorkflow({shops:async options=>{calls.push(options);return {page:1,page_size:10,total:0,shops:[]};}},{initialQuery:'  Synthetic Shop  '});
      try{await workflow.start();assert.equal(calls[0].q,'Synthetic Shop');assert.equal(calls[0].page,1);assert.equal(workflow.getSnapshot().q,'Synthetic Shop');}finally{workflow.dispose();}
    });
    await t.test('delivery join uses only existing JWT endpoints, allowlists fields, and fails closed',async()=>{
      const {default:api}=await load('services/api.js'),{getMyDeliveryPage}=await load('services/customerDeliveryService.js');
      const previous=api.defaults.adapter,storage=globalThis.localStorage,calls=[];globalThis.localStorage={getItem:()=> 'synthetic-session'};
      let wrong=false,networkFailure=false;
      api.defaults.adapter=async config=>{
        calls.push(config);
        if(config.url==='/customer/orders')return {data:page([order(),order({order_id:8})]),status:200,statusText:'OK',headers:{},config};
        if(networkFailure)throw {response:{status:503}};
        const id=Number(config.url.split('/')[3]);
        return {data:{order_id:wrong?999:id,delivery_requested:id===7,delivery:id===7?{reference:'DEL-SYNTHETIC',status:'assigned',created_at:'2026-11-08T10:00:00',updated_at:'2026-11-08T10:00:00',events:[{status:'assigned',occurred_at:'2026-11-08T10:00:00'}],driver_phone:'PRIVATE'}:null},status:200,statusText:'OK',headers:{},config};
      };
      try{
        const signal=new AbortController().signal,result=await getMyDeliveryPage(1,{signal});
        assert.equal(result.orderTotal,2);assert.equal(result.records.length,1);assert.ok(!JSON.stringify(result).includes('PRIVATE'));
        assert.deepEqual(calls.map(c=>c.url),['/customer/orders','/customer/orders/7/delivery','/customer/orders/8/delivery']);
        assert.deepEqual(calls[0].params,{page:1,page_size:10});for(const call of calls){assert.equal(call.headers.Authorization,'Bearer synthetic-session');assert.equal(call.signal,signal);}
        wrong=true;await assert.rejects(getMyDeliveryPage(1));wrong=false;networkFailure=true;await assert.rejects(getMyDeliveryPage(1));
      }finally{api.defaults.adapter=previous;if(storage===undefined)delete globalThis.localStorage;else globalThis.localStorage=storage;}
    });
  } finally {await server.close();}
});
