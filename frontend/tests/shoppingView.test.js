import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
import {createServer} from 'vite';
import {readFile} from 'node:fs/promises';
test('shopping actual React views and integration contracts',async t=>{
const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
try{
 const {ShoppingContext}=await server.ssrLoadModule('/src/context/ShoppingContext.js');
 const {default:Cart}=await server.ssrLoadModule('/src/pages/customer/ShoppingCart.jsx');
 const {default:Add}=await server.ssrLoadModule('/src/components/customer/AddToCart.jsx');
 const {OrderRecord}=await server.ssrLoadModule('/src/pages/customer/OrderHistory.jsx');
 const value={cart:{business_id:2,items:[{product_id:1,business_id:2,name:'Rice',quantity:2}]},pending:null};
 const render=(Component,props={},context=value)=>renderToStaticMarkup(h(MemoryRouter,null,h(ShoppingContext.Provider,{value:context},h(Component,props))));
 await t.test('cart quantities, removal and estimated total guidance',()=>{const html=render(Cart);for(const text of ['Shopping Cart','Quantity for Rice','Remove Rice','Clear cart','estimates','Checking current prices'])assert.ok(html.includes(text),text);});
 await t.test('checkout separates cash and credit from payment and approval',()=>{const html=render(Cart,{checkout:true});for(const text of ['Checkout','Cash — offline, unpaid','Credit — requires Shop Owner approval','No online payment','Credit submission creates no debt','Place Order'])assert.ok(html.includes(text),text);});
 await t.test('empty cart is safe and pending retry remains visible',()=>{assert.ok(render(Cart,{}, {...value,cart:{business_id:null,items:[]}}).includes('Your cart is empty'));assert.ok(render(Cart,{checkout:true},{...value,pending:{request_key:'fixture'}}).includes('Retry same order'));});
 await t.test('reopened unconfirmed credit checkout displays the frozen Credit selection',()=>{const html=render(Cart,{checkout:true},{...value,pending:{payment_method:'credit',request_key:'fixture'}});assert.match(html,/<input(?=[^>]*value="credit")(?=[^>]*checked)[^>]*>/);assert.doesNotMatch(html,/<input(?=[^>]*value="cash")(?=[^>]*checked)[^>]*>/);});
 await t.test('catalogue add availability and pending request prevention',()=>{const p={product_id:1,business_id:2,name:'Rice',availability_status:'available'};assert.ok(render(Add,{product:p}).includes('Add to Cart'));assert.match(render(Add,{product:{...p,availability_status:'unavailable'}}),/disabled/);assert.match(render(Add,{product:p},{...value,pending:{}}),/disabled/);});
 const order={order_id:7,reference:'ORD-fixture',business_name:'Local Shop',customer_name:'Customer <safe>',status:'submitted',payment_method:'credit',payment_status:'pending',total:'250.50',created_at:'2026-11-07T00:00:00',items:[{product_id:1,product_name:'Rice',quantity:2,unit_price:'125.25',line_total:'250.50'}],credit_sale_id:null};
 await t.test('owner details expose approval and rejection while customer details allow only cancellation',()=>{let html=render(OrderRecord,{order,owner:true});for(const text of ['Approve Credit','Reject Order','Cancel Order','LKR 250.50','Customer &lt;safe&gt;','Payment:'])assert.ok(html.includes(text),text);html=render(OrderRecord,{order});assert.ok(!html.includes('Approve Credit'));assert.ok(html.includes('Cancel Order'));assert.ok(!html.includes('Customer &lt;safe&gt;'));});
 await t.test('cash processing never claims paid; completed immutable',()=>{let html=render(OrderRecord,{order:{...order,payment_method:'cash',payment_status:'unpaid'},owner:true});assert.ok(html.includes('Process Order'));assert.ok(html.includes('unpaid'));assert.ok(!html.includes('Approve Credit'));html=render(OrderRecord,{order:{...order,status:'completed'},owner:true});assert.ok(!html.includes('<button'));});
 await t.test('real routes, guarded layouts and authoritative payload construction',async()=>{const app=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');for(const route of ['cart','checkout','orders','orders/:orderId'])assert.ok(app.includes('path="'+route+'"'));const source=await readFile(new URL('../src/pages/customer/ShoppingCart.jsx',import.meta.url),'utf8');assert.ok(source.includes('lock.current'));assert.ok(source.includes('checkoutPayload(cart,quote,method,crypto.randomUUID(),selectedMode)'));assert.ok(source.includes('cartPayload(cart)'));assert.ok(!source.includes('localStorage'));const service=await readFile(new URL('../src/services/orderService.js',import.meta.url),'utf8');assert.ok(service.includes('/customer/orders/quote'));assert.ok(service.includes('/shop-owner/orders'));});
}finally{await server.close();}
});
