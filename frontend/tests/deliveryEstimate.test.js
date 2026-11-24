import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
import {validDeliveryEstimate} from '../src/utils/deliveryEstimate.js';
import {cartPayload} from '../src/utils/shopping.js';
import {parseDriverResponse} from '../src/utils/driverDashboard.js';
import {driverFixtures} from './fixtures/driverDashboardFixtures.js';

test('display estimates validate exact backend rounding; submission excludes all estimated amounts',()=>{
  for(const row of [['5000.00','150.00','5150.00'],['0.50','0.02','0.52'],['0.15','0.00','0.15'],['100.99','3.03','104.02']])assert.ok(validDeliveryEstimate(...row));
  assert.ok(!validDeliveryEstimate('0.50','0.01','0.51'));
  assert.ok(!validDeliveryEstimate('5000.00','150.00','5000.00'));
  assert.deepEqual(cartPayload({business_id:10,estimated_total_with_delivery:'5150.00',items:[{product_id:1,quantity:1,estimated_delivery_fee:'150.00'}]}),{business_id:10,items:[{product_id:1,quantity:1}]});
});

test('Driver estimates remain per unique authorized delivery, never earnings summary totals',()=>{
  const data=driverFixtures().deliveries;
  const row=data.deliveries[0];
  const response={...data,deliveries:[{...row,linked_order_subtotal:'5000.00',estimated_delivery_earning:'150.00'}],total:1};
  assert.equal(parseDriverResponse('deliveries',response,7).deliveries[0].estimated_delivery_earning,'150.00');
  assert.throws(()=>parseDriverResponse('deliveries',{...response,deliveries:[{...response.deliveries[0],estimated_delivery_earning:'5150.00'}]},7));
  assert.throws(()=>parseDriverResponse('deliveries',{...response,deliveries:[response.deliveries[0],response.deliveries[0]],total:2},7));
  assert.equal(parseDriverResponse('summary',{...driverFixtures().summary,estimated_delivery_earning:'150.00'},7).estimated_delivery_earning,undefined);
});

test('Checkout and Driver Dashboard label estimates separately from actual payable and earnings',async()=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try {
    const {CheckoutTotals}=await server.ssrLoadModule('/src/pages/customer/ShoppingCart.jsx');
    const html=renderToStaticMarkup(h(CheckoutTotals,{quote:{subtotal:'5000.00',total:'5000.00',estimated_delivery_fee:'150.00',estimated_total_with_delivery:'5150.00'}}));
    for(const text of ['Estimated Delivery Fee (3%)','Estimated Total Including Delivery','Actual Order Amount Payable','LKR 150.00','LKR 5,150.00','not charged or recorded as earnings'])assert.ok(html.includes(text),text);
    const {DriverDashboardView}=await server.ssrLoadModule('/src/pages/driver/DriverDashboard.jsx');
    const fixtures=driverFixtures();fixtures.deliveries.deliveries[0].estimated_delivery_earning='150.00';
    const state={authError:'',...Object.fromEntries(Object.entries(fixtures).map(([k,data])=>[k,{data,loading:false,error:''}]))};
    const driver=renderToStaticMarkup(h(MemoryRouter,null,h(DriverDashboardView,{state,actions:{start(){},load(){}}})));
    assert.match(driver,/Estimated Delivery Earning/);assert.match(driver,/LKR 150.00/);
    assert.match(driver,/not credited, collected or paid/);assert.match(driver,/Earnings accounting is not available/);
  } finally {await server.close();}
});
