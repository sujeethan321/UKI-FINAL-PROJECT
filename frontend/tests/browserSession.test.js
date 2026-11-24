import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {browserLoginLock} from '../src/utils/authSession.js';

test('browser lock fails closed when unavailable and uses one exclusive origin lock',async()=>{
 const previous=Object.getOwnPropertyDescriptor(globalThis,'navigator');
 try {
  Object.defineProperty(globalThis,'navigator',{configurable:true,value:{}});
  let calls=0;
  await assert.rejects(browserLoginLock(()=>calls++),{code:'BROWSER_SESSION_LOCK_UNAVAILABLE'});
  assert.equal(calls,0);
  Object.defineProperty(globalThis,'navigator',{configurable:true,value:{locks:{request:async(name,options,operation)=>{
   assert.equal(name,'lankapex:browser-login');assert.equal(options.mode,'exclusive');return operation();
  }}}});
  await browserLoginLock(()=>calls++);assert.equal(calls,1);
 }finally{if(previous)Object.defineProperty(globalThis,'navigator',previous);else delete globalThis.navigator;}
});

test('API uses shared authentication and prevents requests from stale account pages',async()=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 const savedStorage=globalThis.localStorage,savedWindow=globalThis.window;
 try {
  let token='account-one';const events=[];
  globalThis.localStorage={getItem:()=>token,removeItem:()=>{token=null;}};
  globalThis.window={dispatchEvent:event=>events.push(event.type)};
  const {default:api,setAuthTokenReader}=await server.ssrLoadModule('/src/services/api.js');
  let calls=0;
  api.defaults.adapter=async config=>{calls++;return {config,status:200,statusText:'OK',headers:{},data:{}};};
  setAuthTokenReader(()=> 'account-one');
  const response=await api.get('/auth/me');assert.equal(response.config.headers.get('Authorization'),'Bearer account-one');
  token='account-two';
  await assert.rejects(api.post('/shop-owner/repayments',{}));
  assert.equal(calls,1);assert.ok(events.includes('lankapex:session-changed'));
  // Identity verification explicitly supplies the token being restored.
  const verified=await api.get('/auth/me',{headers:{Authorization:'Bearer account-two'}});
  assert.equal(verified.config.headers.get('Authorization'),'Bearer account-two');
  api.defaults.adapter=async config=>{throw {config,response:{status:401}};};
  await assert.rejects(api.get('/auth/me',{headers:{Authorization:'Bearer account-one'}}));
  assert.equal(token,'account-two');
  await assert.rejects(api.get('/auth/me',{headers:{Authorization:'Bearer account-two'}}));
  assert.equal(token,null);assert.ok(events.includes('lankapex:session-expired'));
 } finally {
  if(savedStorage===undefined)delete globalThis.localStorage;else globalThis.localStorage=savedStorage;
  if(savedWindow===undefined)delete globalThis.window;else globalThis.window=savedWindow;
  await server.close();
 }
});
