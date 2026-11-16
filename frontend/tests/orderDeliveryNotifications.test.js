import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
import {createServer} from 'vite';
import {notificationDestination,validNotification,NOTIFICATION_TYPES} from '../src/utils/notification.js';
import {bindNotificationLifecycle,createNotificationWorkflow} from '../src/utils/notificationWorkflow.js';
import {NOTIFICATION_CHANGE_EVENT,notificationChanged} from '../src/utils/notificationChange.js';
const row=(kind='delivery_assigned',entity='delivery_request')=>({notification_id:1,business_id:12,notification_type:kind,title:'Delivery update',message:'The delivery has a recorded update.',related_entity_type:entity,related_entity_id:40,is_read:false,created_at:'2026-11-07T08:00:00Z',read_at:null});
for(const kind of ['delivery_requested','delivery_assigned','delivery_picked_up','delivery_in_transit','delivery_delivered','delivery_cancelled'])test('Customer delivery event links only to authorized Order Details: '+kind,()=>{const n=row(kind,'order');assert.ok(validNotification(n));assert.deepEqual(notificationDestination({...n,url:'https://evil.example'},'customer'),{to:'/customer/orders/40',label:'View order'});assert.equal(notificationDestination(n,'driver'),null);});
test('owner and Driver delivery links use existing guarded routes; Customer never gets a Driver page',()=>{const n=row();assert.equal(notificationDestination(n,'shop_owner').to,'/shop-owner/deliveries?business_id=12&delivery_id=40');assert.equal(notificationDestination(n,'driver').to,'/driver/deliveries/40');assert.equal(notificationDestination(n,'customer'),null);assert.equal(notificationDestination({...n,related_entity_id:-1},'driver'),null);assert.equal(notificationDestination({...n,business_id:null},'driver'),null);assert.equal(validNotification(row('order_submitted','delivery_request')),false);});
test('new filters registered without inventing ready or external message events',()=>{assert.ok(NOTIFICATION_TYPES.some(([type])=>type==='delivery_requested'));assert.ok(NOTIFICATION_TYPES.some(([type])=>type==='delivery_cancelled'));assert.ok(!NOTIFICATION_TYPES.some(([type])=>['order_ready','sms_sent'].includes(type)));});
test('local invalidation refreshes once per successful event, ignores hidden tabs, cleans up on logout',()=>{const win=new EventTarget(),doc=new EventTarget();doc.hidden=false;let refreshed=0,disposed=0;const workflow={start(){},setVisible(){},returnToTab(){},refreshAfterChange(){refreshed++;},dispose(){disposed++;}};const cleanup=bindNotificationLifecycle(workflow,win,doc);win.dispatchEvent(new Event(NOTIFICATION_CHANGE_EVENT));assert.equal(refreshed,1);doc.hidden=true;win.dispatchEvent(new Event(NOTIFICATION_CHANGE_EVENT));assert.equal(refreshed,1);cleanup();win.dispatchEvent(new Event(NOTIFICATION_CHANGE_EVENT));assert.equal(refreshed,1);assert.equal(disposed,1);});
test('change signal contains no business/order/private payload and preserves confirmed data',()=>{const original=globalThis.window,win=new EventTarget();globalThis.window=win;let event;win.addEventListener(NOTIFICATION_CHANGE_EVENT,value=>event=value);try{const data={order_id:7,private:'TEST-ONLY'};assert.equal(notificationChanged(data),data);assert.equal(event.detail,undefined);}finally{if(original===undefined)delete globalThis.window;else globalThis.window=original;}});
test('actual notification rendering, inbox filters and mutation API refresh hooks',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
 const {default:Item}=await server.ssrLoadModule('/src/components/notifications/NotificationItem.jsx');
 for(const role of ['customer','shop_owner','driver'])await t.test(role+' renders its authorized linked notification with read controls',()=>{const notification=row('delivery_assigned',role==='customer'?'order':'delivery_request');const html=renderToStaticMarkup(h(MemoryRouter,null,h(Item,{notification,role,busy:false})));assert.ok(html.includes('Mark as Read'));assert.ok(html.includes('Unread'));assert.ok(html.includes('href="'+notificationDestination(notification,role).to.replaceAll('&','&amp;')+'"'));assert.ok(!html.includes('https://'));});
 await t.test('actual action services refresh only after confirmed POSTs, never failed requests or GETs',async()=>{
 const {default:api}=await server.ssrLoadModule('/src/services/api.js');
 const [orders,jobs,deliveries,owner]=await Promise.all(['/src/services/orderService.js','/src/services/driverJobsService.js','/src/services/driverDeliveriesService.js','/src/services/shopOwnerDeliveryService.js'].map(p=>server.ssrLoadModule(p)));
 const oldWindow=globalThis.window,oldStorage=globalThis.sessionStorage,adapter=api.defaults.adapter;
 const win=new EventTarget();let events=0;win.addEventListener(NOTIFICATION_CHANGE_EVENT,()=>events++);globalThis.window=win;globalThis.sessionStorage={getItem:()=>null};
 api.defaults.adapter=async config=>({data:{confirmed:true},status:200,statusText:'OK',headers:{},config});
 try{
  await orders.placeOrder({});await orders.decideOrder(true,7,12,'process');await orders.requestOrderDelivery(7,12,{pickup_area:'Area',delivery_area:'Area'});await jobs.acceptDriverJob(40);await deliveries.updateDriverDelivery(40,{expected_status:'assigned',status:'picked_up'});await owner.cancelShopDelivery(12,40);
  assert.equal(events,6);
  await orders.customerOrderDelivery(7);await deliveries.readDriverDelivery(40);assert.equal(events,6);
  api.defaults.adapter=async()=>{throw {response:{status:409}};};await assert.rejects(()=>orders.requestOrderDelivery(7,12,{}));assert.equal(events,6);
 }finally{api.defaults.adapter=adapter;if(oldWindow===undefined)delete globalThis.window;else globalThis.window=oldWindow;if(oldStorage===undefined)delete globalThis.sessionStorage;else globalThis.sessionStorage=oldStorage;}
 });
 }finally{await server.close();}
});

test('mark-read confirmation cannot switch an Order destination into a delivery destination',async()=>{
 const original=row('delivery_assigned','order');
 const api={count:async()=>({unread_count:1}),list:async filters=>({page:filters.page,page_size:filters.page_size,total:1,notifications:[original]}),markOne:async()=>({...original,related_entity_type:'delivery_request',is_read:true,read_at:'2026-11-07T09:00:00Z'})};
 const workflow=createNotificationWorkflow({api});workflow.start();workflow.openInbox();await workflow.loadList();await workflow.markRead(1);
 assert.ok(workflow.getSnapshot().actionError);assert.equal(workflow.getSnapshot().list.notifications[0].is_read,false);assert.equal(workflow.getSnapshot().list.notifications[0].related_entity_type,'order');workflow.dispose();
});

test('domain changes invalidate older unread reads instead of coalescing stale counts',async()=>{
 let resolve;const first=new Promise(r=>resolve=r);let calls=0;
 const workflow=createNotificationWorkflow({api:{count:async()=>++calls===1?first:{unread_count:1}}});
 workflow.start();await workflow.refreshAfterChange();assert.equal(workflow.getSnapshot().count,1);resolve({unread_count:99});await first;await new Promise(r=>setTimeout(r,0));assert.equal(workflow.getSnapshot().count,1);workflow.dispose();
});
