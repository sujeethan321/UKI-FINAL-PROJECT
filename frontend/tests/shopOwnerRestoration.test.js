import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
import {createServer} from 'vite';

test('restored Shop Owner views retain real-data and unavailable-feature boundaries',async t=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try {
    const load=path=>server.ssrLoadModule('/src/'+path);
    const render=(View,props)=>renderToStaticMarkup(h(MemoryRouter,null,h(View,props)));
    const businesses=[{business_id:72,business_name:'Synthetic Corner Shop',business_type:'retail',approval_status:'approved'}];
    await t.test('all ten navigation destinations are enabled without the removed shop footer',async()=>{
      const {default:Sidebar}=await load('components/shopOwner/ShopOwnerSidebar.jsx');
      const html=render(Sidebar,{business:businesses[0],businessCount:1});
      for(const path of ['dashboard','customers','credit-sales','repayments','orders','deliveries','products','reports','notifications','settings'])assert.ok(html.includes('href="/shop-owner/'+path+'"'),path);
      assert.doesNotMatch(html,/Synthetic Corner Shop|coming soon|Perera Grocery/);
    });
    await t.test('dashboard has three financial cards; missing values remain unavailable',async()=>{
      const {default:Cards}=await load('components/shopOwner/OverviewCards.jsx');
      const html=render(Cards,{summary:{total_outstanding:'321.45',collected_today:null,overdue_amount:null,credit_customers:8}});
      assert.equal((html.match(/<article/g)||[]).length,3);assert.match(html,/321.45/);assert.doesNotMatch(html,/Credit Customers/);
      assert.match(html,/Unavailable/);assert.doesNotMatch(html,/Data not connected yet/);
      const confirmed=render(Cards,{summary:{total_outstanding:'70.05',collected_today:'30.05',overdue_amount:'0.00'}});
      for(const amount of ['LKR 70.05','LKR 30.05','LKR 0.00'])assert.ok(confirmed.includes(amount),amount);
      assert.doesNotMatch(confirmed,/Unavailable|Data not connected yet/);
      const {default:Attention}=await load('components/shopOwner/NeedsAttention.jsx');
      const attention=render(Attention,{summary:{credit_customers:8},businessId:72});
      assert.match(attention,/Count unavailable/);assert.doesNotMatch(attention,/12 Overdue|3 Unassigned/);
    });
    await t.test('reports show API figures without invented charts or export actions',async()=>{
      const {ShopOwnerReportsView:View}=await load('pages/shopOwner/ShopOwnerReports.jsx');
      const html=render(View,{businesses,businessId:72,summary:{total_outstanding:'123.45'},loading:false,error:''});
      for(const text of ['Financial Overview','Credit Sales Trend','Repayment Trend','Outstanding Credit Aging','123.45','Export Report'])assert.ok(html.includes(text),text);
      assert.match(html,/disabled/);assert.match(html,/stored database wall clock/);assert.doesNotMatch(html,/<svg[^>]+role="img"|185,000/);
    });
    await t.test('settings expose recorded identity and working links without fake save/security controls',async()=>{
      const {ShopOwnerSettingsView:View}=await load('pages/shopOwner/ShopOwnerSettings.jsx');
      const html=render(View,{businesses,businessId:72,user:{account_status:'active',preferred_language:'en'}});
      for(const text of ['Synthetic Corner Shop','Shop Settings','Credit &amp; Delivery Preferences','Notifications &amp; Language','Account &amp; Security','Sign Out'])assert.ok(html.includes(text),text);
      assert.match(html,/readOnly/);assert.doesNotMatch(html,/Save Preferences|Save Shop Details|>Verified</);
      assert.match(html,/href="\/shop-owner\/customers"/);
    });
    await t.test('owner inbox hides prior private records after authorization failure',async()=>{
      const {ShopOwnerInboxView:View}=await load('components/shopOwner/ShopOwnerInbox.jsx');
      const state={readFilter:'all',typeFilter:'',count:null,authError:'Session expired',page:1,pageSize:10,list:{total:1,notifications:[{notification_id:1,created_at:'2026-11-08T10:00:00Z',title:'PRIVATE-OLD-DATA'}]}};
      const html=render(View,{state,actions:{}});
      assert.match(html,/Session expired/);assert.doesNotMatch(html,/PRIVATE-OLD-DATA/);assert.match(html,/— Unread/);
    });
    await t.test('Owner orders render a table while Customer details keep their existing view',async()=>{
      const {ShopOwnerOrderTable:Table,OrderRecord}=await load('pages/customer/OrderHistory.jsx');
      const order={order_id:1,reference:'ORDER-SYNTHETIC',customer_name:'Synthetic Customer',business_name:'Synthetic Shop',status:'pending_approval',payment_method:'credit',payment_status:'unpaid',total:'12.50',created_at:'2026-11-08T10:00:00',items:[{product_id:1,product_name:'Synthetic Product',quantity:1,unit_price:'12.50',line_total:'12.50'}]};
      const html=render(Table,{orders:[order],business:72});assert.match(html,/<table/);assert.match(html,/ORDER-SYNTHETIC/);
      const customer=render(OrderRecord,{order});assert.match(customer,/<ul/);assert.doesNotMatch(customer,/Ordered Products|<table/);
      const owner=render(OrderRecord,{order,owner:true});assert.match(owner,/Ordered Products/);assert.match(owner,/<table/);
    });
  } finally { await server.close(); }
});
