import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
import {createServer} from 'vite';
import {parseEarnings} from '../src/utils/driverFinance.js';
import {checkoutPayload} from '../src/utils/shopping.js';
const fixture=()=>({driver_user_id:5,currency:'LKR',total:1,page:1,page_size:20,period:'month',
 summary:{pending:'0.00',declared:'0.00',directly_settled:'150.00',review:'0.00',total_earned:'150.00',available:'0.00',platform_paid:'0.00',platform_payout_supported:false},
 daily:[{date:'2026-11-23',earned:'150.00'}],earnings:[{earning_id:'fictional-earning',driver_user_id:5,delivery_request_id:1,amount:'150.00',status:'directly_settled',
  platform_payout_supported:false,collection_verified:true,directly_settled:true,created_at:'2026-11-23T10:00:00',collections:[],settlement_events:[]}]});

test('finance response rejects other Drivers, fake payout availability and malformed amounts',()=>{
 assert.equal(parseEarnings(fixture(),5).summary.directly_settled,'150.00');
 for(const change of [d=>d.driver_user_id=9,d=>d.earnings[0].driver_user_id=9,d=>d.summary.available='150.00',d=>d.summary.platform_paid='150.00',d=>d.earnings[0].amount='NaN',d=>d.earnings.push(d.earnings[0])]){
  const data=fixture();change(data);assert.throws(()=>parseEarnings(data,5));
 }
});

test('checkout sends explicit fulfilment and signed acceptance, never client-authoritative totals',()=>{
 const cart={business_id:10,items:[{product_id:1,quantity:1}]};
 const quote={business_id:10,fulfilment_mode:'delivery',fee_policy:'direct-driver-3pct-v1',quote_token:'signed-quote',delivery_fee:'150.00',customer_total:'5150.00'};
 const payload=checkoutPayload(cart,quote,'credit','request-key','delivery');
 assert.equal(payload.quote_token,'signed-quote');assert.equal(payload.payment_method,'credit');
 for(const key of ['delivery_fee','customer_total','total','subtotal'])assert.ok(!Object.hasOwn(payload,key));
 assert.throws(()=>checkoutPayload(cart,quote,'cash','request-key','pickup'));
 assert.throws(()=>checkoutPayload({...cart,business_id:20},quote,'cash','request-key','delivery'));
 const legacy=checkoutPayload(cart,{business_id:10,finance_enabled:false},'credit','legacy-request','');
 assert.deepEqual(legacy,{business_id:10,items:[{product_id:1,quantity:1}],payment_method:'credit',request_key:'legacy-request'});
 for(const field of ['fulfilment_mode','quote_token','delivery_fee','customer_total'])assert.ok(!Object.hasOwn(legacy,field));
});

test('existing fee and Earnings containers show actual charges, unavailable states and no second payout',async()=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
  const {DriverEarningsView}=await server.ssrLoadModule('/src/pages/driver/DriverEarnings.jsx');
  const render=props=>renderToStaticMarkup(h(MemoryRouter,null,h(DriverEarningsView,{period:'month',...props})));
  const html=render({data:fixture()});for(const text of ['LKR 150.00','Directly settled','platform','LKR 0.00'])assert.ok(html.includes(text));
  assert.ok(!html.includes('Submit declaration'));
  const loading=render({loading:true});assert.ok(loading.includes('Loading earnings'));assert.ok(!loading.includes('LKR 0.00'));
  const gated=render({loading:false,error:'Driver finance is not enabled.'});assert.ok(gated.includes('not enabled'));assert.ok(!gated.includes('LKR 0.00'));
  const declared=fixture();declared.earnings[0].status='collection_declared';declared.earnings[0].collection_verified=false;declared.earnings[0].directly_settled=false;
  const declaredHTML=render({data:declared});assert.ok(declaredHTML.includes('Collection declared'));assert.ok(!declaredHTML.includes('Submit declaration'));
  const {CheckoutTotals}=await server.ssrLoadModule('/src/pages/customer/ShoppingCart.jsx');
  const totals=renderToStaticMarkup(h(CheckoutTotals,{quote:{fee_policy:'direct-driver-3pct-v1',subtotal:'5000.00',delivery_fee:'150.00',customer_total:'5150.00'}}));
  for(const value of ['LKR 5,000.00','LKR 150.00','LKR 5,150.00','paid directly'])assert.ok(totals.includes(value));
  const {default:i18n}=await server.ssrLoadModule('/src/i18n/index.js');
  try {
   for(const language of ['ta','si']){
    await i18n.changeLanguage(language);const localized=render({data:fixture()});
    assert.ok(!localized.includes('Customer pays the Driver directly.'));
    assert.ok(localized.includes('LKR 150.00'));
    assert.match(localized,language==='ta'?/[\u0b80-\u0bff]/:/[\u0d80-\u0dff]/);
   }
  }finally{await i18n.changeLanguage('en');}
 }finally{await server.close();}
});
