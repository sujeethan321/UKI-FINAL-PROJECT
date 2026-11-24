import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {parseAddressBook,parseDestination,createAddressReader,addressError} from '../src/utils/customerAddress.js';
import {checkoutPayload} from '../src/utils/shopping.js';

const row={address_id:1,label:'Home',recipient_name:'Fictional recipient',phone:null,city:null,address_line:'Fictional address\nFloor 2',archived:false};
const book=()=>({version:2,default_address_id:1,addresses:[row],total:1,page:1,page_size:10});
const deferred=()=>{let resolve;const promise=new Promise(yes=>{resolve=yes;});return {promise,resolve};};

test('address projection strips private extras and rejects invalid ownership-independent fields',()=>{
 assert.equal(parseAddressBook(book()).addresses[0].user_id,undefined);
 assert.equal(parseDestination({...row,storage_key:'private'}).storage_key,undefined);
 for(const patch of [{version:0},{addresses:[row,row],total:2},{default_address_id:3},{total:2},{addresses:[{...row,archived:true}]}])assert.throws(()=>parseAddressBook({...book(),...patch}));
});
test('address mutations submit current version and stable create key, never ownership',async()=>{
 const calls=[];const api={listAddresses:async()=>book(),createAddress:async data=>calls.push(data)};
 const reader=createAddressReader(api);await reader.start();
 await reader.save('create',null,{...row,request_key:'synthetic-address-001',user_id:99});
 assert.equal(calls[0].version,2);assert.equal(calls[0].request_key,'synthetic-address-001');assert.equal(calls[0].user_id,undefined);
 reader.dispose();
});
test('late address response is discarded after logout/disposal',async()=>{
 const pending=deferred(),reader=createAddressReader({listAddresses:()=>pending.promise});
 const task=reader.start();reader.dispose();pending.resolve(book());await task;assert.equal(reader.getSnapshot().data,null);
});
test('late mutation is discarded and never reloads after disposal',async()=>{
 let reads=0;const pending=deferred(),reader=createAddressReader({listAddresses:async()=>{reads++;return book();},archiveAddress:()=>pending.promise});
 await reader.start();const task=reader.save('archive',1);reader.dispose();pending.resolve({});await task;assert.equal(reads,1);assert.equal(reader.getSnapshot().data,null);
});
test('conflicts preserve existing address data without retries or raw errors',async()=>{
 let calls=0;const reader=createAddressReader({listAddresses:async()=>book(),defaultAddress:async()=>{calls++;throw {response:{status:409,data:{detail:'private SQL'}}};}});
 await reader.start();await reader.save('default',1);assert.equal(calls,1);assert.match(reader.getSnapshot().error,/Reload/);assert.equal(reader.getSnapshot().data.version,2);reader.dispose();
 assert.ok(!addressError({response:{status:500,data:{detail:'secret'}}}).includes('secret'));
});
test('delivery quote carries destination acceptance; pickup and disabled checkout omit it',()=>{
 const cart={business_id:10,items:[{product_id:1,quantity:1}]};
 const quote={business_id:10,finance_enabled:true,fee_policy:'direct-driver-3pct-v1',fulfilment_mode:'delivery',quote_token:'signed',address_checkout_enabled:true,address_id:1,address_version:2};
 const payload=checkoutPayload(cart,quote,'credit','request-key','delivery');assert.equal(payload.address_id,1);assert.equal(payload.address_version,2);assert.equal(payload.total,undefined);assert.equal(payload.delivery_fee,undefined);
 const pickup=checkoutPayload(cart,{...quote,fulfilment_mode:'pickup'},'cash','request-key','pickup');assert.equal(pickup.address_id,undefined);
 const legacy=checkoutPayload(cart,{business_id:10,finance_enabled:false},'cash','request-key');assert.equal(legacy.address_id,undefined);
 assert.throws(()=>checkoutPayload(cart,{...quote,address_version:null},'cash','request-key','delivery'));
});
test('address locale keys have EN TA SI coverage',async()=>{
 for(const lang of ['en','ta','si']){
  const data=JSON.parse(await readFile(new URL('../src/i18n/locales/application.'+lang+'.json',import.meta.url),'utf8'));
  for(const key of ['Add address','Archive address','Use this address','Confirmed delivery destination','Address management is unavailable on this server.'])assert.ok(data[key]);
 }
});
