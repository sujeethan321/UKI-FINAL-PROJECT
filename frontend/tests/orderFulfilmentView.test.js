import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
import {createServer} from 'vite';
import {readFile} from 'node:fs/promises';
import {deliveryDetail} from './fixtures/shopOwnerDeliveryFixtures.js';
test('existing Order fulfilment React views and routing contracts',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
 const {OrderFulfilmentView:View}=await server.ssrLoadModule('/src/components/shopOwner/OrderFulfilment.jsx');
 const base={loading:false,busy:false,error:'',message:'',formOpen:false,uncertain:false,form:{pickup_area:'',delivery_area:''},data:{order_id:7,delivery_requested:false,delivery:null,can_request_delivery:true,delivery_unavailable_reason:null}};
 const render=(state=base,props={})=>renderToStaticMarkup(h(MemoryRouter,null,h(View,{state,actions:{},businessId:1,...props})));
 await t.test('backend eligible state exposes Request Delivery; pending approval does not',()=>{assert.ok(render().includes('Request Delivery'));assert.ok(!render({...base,data:{...base.data,can_request_delivery:false,delivery_unavailable_reason:'Credit approval required'}}).includes('>Request Delivery<'));});
 await t.test('form uses exact schema and explicitly requests missing areas',()=>{const html=render({...base,formOpen:true});for(const value of ['Pickup area','Delivery destination','name="pickup_area"','name="delivery_area"','required','maxLength="160"','No saved delivery destination','Confirm Request Delivery'])assert.ok(html.includes(value),value);for(const value of ['recipient_phone','coordinates','vehicle_type','type="password"'])assert.ok(!html.includes(value));});
 await t.test('pending submission and uncertain outcome disable edits and duplicate controls',()=>{let html=render({...base,busy:true,formOpen:true});assert.ok(html.includes('Requesting delivery'));assert.match(html,/<input[^>]*disabled/);html=render({...base,uncertain:true,formOpen:true});assert.ok(html.includes('Retry same delivery request'));assert.ok(html.includes('last attempt is unconfirmed'));});
 await t.test('linked assigned Driver and recorded progress reuse tracking UI',()=>{const timestamp='2026-11-06T10:00:00';const delivery=deliveryDetail({status:'assigned',can_cancel:false,assigned_driver:{full_name:'Driver <safe>',assigned_at:timestamp},events:[{status:'assigned',occurred_at:timestamp}]});const html=render({...base,data:{...base.data,delivery,can_request_delivery:false}});for(const value of ['Driver &lt;safe&gt;','Recorded delivery progress','Assigned','View Delivery','business_id=1&amp;delivery_id=31','does not record payment'])assert.ok(html.includes(value),value);assert.ok(!html.includes('Confirm Request Delivery'));});
 await t.test('cancelled history retains link without replacement; delivered never says paid',()=>{for(const status of ['cancelled','delivered']){const html=render({...base,data:{...base.data,delivery:deliveryDetail({status}),can_request_delivery:false}});assert.ok(html.includes(status==='cancelled'?'Replacement delivery requests are not supported':'Delivered'));assert.ok(!html.includes('>Request Delivery<'));assert.ok(!html.includes('Payment received'));}});
 await t.test('loading/error/empty states and compact list eligibility are clear',()=>{assert.ok(render({...base,data:null,loading:true}).includes('Loading delivery eligibility'));assert.ok(render({...base,data:null,error:'Session expired. Please sign in again.'}).includes('role="alert"'));assert.ok(render().includes('No delivery has been requested'));assert.ok(render(base,{compact:true}).includes('Open Order Details'));});
 await t.test('existing scoped routes/navigation, pagination and snapshot prices preserved',async()=>{const source=await readFile(new URL('../src/pages/customer/OrderHistory.jsx',import.meta.url),'utf8');for(const value of ['page_size:10','status?{status}','business_id:business','Order history','View Details','item.unit_price','item.line_total','OrderFulfilment'])assert.ok(source.includes(value),value);const app=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');assert.ok(app.includes('path="orders/:orderId"'));const service=await readFile(new URL('../src/services/orderService.js',import.meta.url),'utf8');assert.ok(service.includes("'/delivery'"));assert.ok(service.includes('params:{business_id}'));});
 }finally{await server.close();}
});
