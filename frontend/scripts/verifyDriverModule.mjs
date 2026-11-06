// Isolated browser-only Driver QA fixtures. All API requests are intercepted.
// Run from the project root: node frontend/scripts/verifyDriverModule.mjs
// Requires a production build and Chrome (CHROME_PATH overrides Windows default).
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../../',import.meta.url)),out=path.join(root,'.server-logs/day12-final-browser');await mkdir(out,{recursive:true});
const server=createServer(async(req,res)=>{try{let name=new URL(req.url,'http://localhost').pathname;const file=path.join(root,'frontend/dist',name.startsWith('/assets/')?name:'/index.html');const data=await readFile(file);res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.png')?'image/png':'text/html');res.end(data);}catch{res.writeHead(404);res.end();}});
await new Promise(resolve=>server.listen(5187,'127.0.0.1',resolve));
const chrome=spawn(process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--no-first-run','--no-default-browser-check','--disable-gpu','--remote-debugging-port=9237','--remote-allow-origins=*','--user-data-dir='+path.join(out,'chrome-profile'),'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws,closing=false;const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
 let page;for(let attempt=0;attempt<60;attempt++){try{page=await(await fetch('http://127.0.0.1:9237/json/new?about:blank',{method:'PUT'})).json();break;}catch{await delay(250);}}assert.ok(page,'Chrome debugging endpoint unavailable');
 ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 let seq=0;const pending=new Map(),events=new Map();
 const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>reject(Error('CDP timeout: '+method)),15000);pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});ws.send(JSON.stringify({id,method,params}));});
 ws.onclose=()=>{for(const command of pending.values())command.reject(Error('Browser closed'));pending.clear();};
 ws.onmessage=event=>{const msg=JSON.parse(event.data);if(msg.id){const p=pending.get(msg.id);pending.delete(msg.id);msg.error?p.reject(Error(JSON.stringify(msg.error))):p.resolve(msg.result);}else events.get(msg.method)?.(msg.params);};
 const evaluate=async expression=>{const result=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;};
 const wait=async(expression)=>{for(let i=0;i<100;i++){try{if(await evaluate('Boolean(document.body) && ('+expression+')'))return;}catch(error){if(!error.message.includes('Execution context was destroyed')&&!error.message.includes('Cannot find context'))throw error;}await delay(100);}throw Error('Browser condition timed out: '+expression+'\n'+await evaluate('document.body?.innerText'));};
 const now='2026-11-06T10:00:00';let status='assigned',mutations=0,accepted=false,mode='normal';const progress=[];
 const profile={driver_user_id:7,full_name:'Browser QA Driver',account_status:'active',approval_status:'approved',eligible_for_jobs:true,eligibility_reason:'eligible',vehicle:{vehicle_type:'van',registration_reference:'QA-123'}};
 const delivery=()=>({delivery_request_id:31,reference:'DR-BROWSER-ASSIGNED',business_name:'Browser QA Shop',pickup_area:'A long pickup area used to verify responsive wrapping at all required screen widths',delivery_area:'Delivery destination area',status,assigned_at:now,finished_at:status==='delivered'?progress.at(-1).occurred_at:null});
 const detail=()=>({driver_user_id:7,assignment_id:4,delivery:delivery(),events:[{status:'assigned',occurred_at:now},...progress],allowed_next_status:({assigned:'picked_up',picked_up:'in_transit',in_transit:'delivered'})[status]||null});
 const secondDelivery=()=>({...delivery(),delivery_request_id:32,reference:'DR-BROWSER-ACCEPTED',status:'assigned',finished_at:null});
 const availableJob=()=>({delivery_request_id:32,reference:'DR-BROWSER-ACCEPTED',business_name:'Browser QA Shop',pickup_area:'Available pickup area',delivery_area:'Available destination area',status:'available',created_at:now});
 const activeRows=()=>[...(status!=='delivered'?[delivery()]:[]),...(accepted?[secondDelivery()]:[])];
 const reply=async(event,data,code=200)=>send('Fetch.fulfillRequest',{requestId:event.requestId,responseCode:code,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'http://127.0.0.1:5187'},{name:'Access-Control-Allow-Methods',value:'GET,POST,OPTIONS'},{name:'Access-Control-Allow-Headers',value:'authorization,content-type'}],body:Buffer.from(JSON.stringify(data)).toString('base64')});
 events.set('Fetch.requestPaused',async event=>{
  try {
  const url=new URL(event.request.url),endpoint=url.pathname.replace('/api/v1','');let data={},code=200;
  if(endpoint.startsWith('/driver/')&&event.request.method!=='OPTIONS'){
   if(mode==='error')return await reply(event,{detail:'QA service unavailable'},503);
   if(mode==='slow')await delay(1500);
  }
  if(event.request.method==='OPTIONS')data={};
  else if(endpoint==='/auth/me')data={user_id:7,full_name:profile.full_name,platform_role:'driver',account_status:'active'};
  else if(endpoint==='/driver/profile')data=profile;
  else if(endpoint==='/driver/dashboard/summary')data={driver_user_id:7,available_jobs_count:accepted?0:1,active_deliveries_count:activeRows().length,completed_deliveries_count:status==='delivered'?1:0};
  else if(endpoint==='/notifications/unread-count')data={unread_count:0};
  else if(endpoint==='/driver/deliveries/31/status'){
   const payload=JSON.parse(event.request.postData);assert.equal(payload.expected_status,status);mutations++;status=payload.status;progress.push({status,occurred_at:'2026-11-06T1'+mutations+':00:00'});data=detail();
  }else if(endpoint==='/driver/deliveries/31')data=detail();
  else if(endpoint==='/driver/jobs/32')data={driver_user_id:7,job:availableJob()};
  else if(endpoint==='/driver/jobs/32/accept'){
   assert.deepEqual(JSON.parse(event.request.postData),{});accepted=true;data={driver_user_id:7,assignment_id:5,delivery:secondDelivery()};
  }
  else if(endpoint==='/driver/deliveries/32')data={driver_user_id:7,assignment_id:5,delivery:secondDelivery()};
  else if(['/driver/history','/driver/deliveries'].includes(endpoint)){const history=endpoint.endsWith('history');let rows=history?(status==='delivered'?[delivery()]:[]):activeRows();if(url.searchParams.get('status'))rows=rows.filter(row=>row.status===url.searchParams.get('status'));data={driver_user_id:7,total:rows.length,page:Number(url.searchParams.get('page')||1),page_size:Number(url.searchParams.get('page_size')||10),deliveries:rows};}
  else if(endpoint==='/driver/jobs')data={driver_user_id:7,total:accepted?0:1,page:1,page_size:10,jobs:accepted?[]:[availableJob()]};
  else {code=404;data={detail:'QA fixture unavailable'};}
  await reply(event,data,code);
  }catch(error){if(!closing&&!error.message.includes('Invalid InterceptionId'))throw error;}
 });
 await send('Page.enable');await send('Page.bringToFront');await send('Runtime.enable');await send('Fetch.enable',{patterns:[{urlPattern:'http://127.0.0.1:8000/*'}]});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:"sessionStorage.setItem('lankapex_access_token','browser-qa-fixture')"});
 const results=[];
 for(const width of [1536,1366,1024,768,375]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:960,deviceScaleFactor:1,mobile:false});
  for(const route of ['dashboard','jobs','deliveries','deliveries/31','history']){
   await send('Page.navigate',{url:'http://127.0.0.1:5187/driver/'+route});
   await wait(route==='history'?"document.body.innerText.includes('No completed or cancelled deliveries')":route==='jobs'?"document.body.innerText.includes('DR-BROWSER-ACCEPTED')":"document.body.innerText.includes('DR-BROWSER-ASSIGNED')");
   await delay(150);const sizes=await evaluate('({viewport:innerWidth,document:document.documentElement.scrollWidth,body:document.body.scrollWidth})');assert.ok(sizes.document<=width&&sizes.body<=width,JSON.stringify({width,route,...sizes}));
   const clipped=await evaluate(`Array.from(document.querySelectorAll('p,h3,button')).filter(el=>el.getBoundingClientRect().width&&/DR-BROWSER/.test(el.textContent)&&el.children.length===0).some(el=>el.scrollWidth>el.clientWidth+1)`);assert.equal(clipped,false,'Clipped delivery reference: '+route+' '+width);
   const overlap=await evaluate(`(()=>{const boxes=[...document.querySelectorAll('article')].map(el=>el.getBoundingClientRect()).filter(r=>r.width&&r.height);return boxes.some((a,i)=>boxes.slice(i+1).some(b=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top));})()`);assert.equal(overlap,false,'Overlapping cards');
   const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(path.join(out,width+'-'+route.replaceAll('/','-')+'.png'),Buffer.from(shot.data,'base64'));results.push({width,route,overflow:false,clippedReference:false,overlappingCards:false});
   if(width<1024){
    await evaluate(`document.querySelector('[aria-label="Open driver menu"]').click()`);await wait(`document.querySelector('dialog').open`);
    assert.ok(await evaluate(`document.querySelector('dialog').getBoundingClientRect().right<=innerWidth`));
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27,nativeVirtualKeyCode:27});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27,nativeVirtualKeyCode:27});await wait(`!document.querySelector('dialog').open`);
   }
  }
 }
 await send('Page.navigate',{url:'http://127.0.0.1:5187/driver/jobs'});await wait("document.body.innerText.includes('Accept Job')");
 const click=label=>evaluate(`(()=>{const button=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)});if(!button)throw Error('Button missing');button.click();return true;})()`);
 await click('View Details');await wait("document.body.innerText.includes('Delivery Job Details')");await click('Accept Job');await wait("document.body.innerText.includes('Assignment confirmed')");assert.equal(accepted,true);await wait("document.body.innerText.includes('No available delivery jobs right now.')");
 await evaluate(`document.querySelector('a[href="/driver/deliveries"]').click()`);await wait("document.body.innerText.includes('DR-BROWSER-ACCEPTED')");
 await send('Page.navigate',{url:'http://127.0.0.1:5187/driver/deliveries/31'});await wait("document.body.innerText.includes('Confirm Pickup')");
 await click('Confirm Pickup');await wait("document.body.innerText.includes('Start Delivery')");assert.equal(mutations,1);
 await click('Start Delivery');await wait("document.body.innerText.includes('Mark Delivered')");assert.equal(mutations,2);
 await click('Mark Delivered');await wait("document.body.innerText.includes('Confirm this delivery has reached its destination?')");assert.equal(mutations,2);
 await click('Cancel');assert.equal(mutations,2);await click('Mark Delivered');await click('Confirm Delivered');await wait("document.body.innerText.includes('No further status updates')");assert.equal(mutations,3);await wait("document.body.innerText.includes('Active deliveries: 1')");
 await send('Page.navigate',{url:'http://127.0.0.1:5187/driver/history'});await wait("document.body.innerText.includes('DR-BROWSER-ASSIGNED')");
 assert.ok((await evaluate('document.body.innerText')).includes('Delivered'));
 for(const route of ['dashboard','jobs','deliveries','deliveries/31','history']){
  mode='slow';await send('Page.navigate',{url:'http://127.0.0.1:5187/driver/'+route});await wait(`document.querySelector('[role="status"]') && /Loading|Checking|Refreshing/.test(document.body.innerText)`);await delay(1700);
  mode='error';await send('Page.navigate',{url:'http://127.0.0.1:5187/driver/'+route});await wait(`document.body.innerText.includes('unavailable')`);
 }
 mode='normal';await send('Page.navigate',{url:'http://127.0.0.1:5187/driver/history'});await wait("document.body.innerText.includes('DR-BROWSER-ASSIGNED')");
 await evaluate(`document.activeElement?.blur()`);await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9,nativeVirtualKeyCode:9});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9,nativeVirtualKeyCode:9});
 assert.ok(await evaluate(`getComputedStyle(document.activeElement).outlineStyle!=='none' && parseFloat(getComputedStyle(document.activeElement).outlineWidth)>0`),'Keyboard focus indicator missing');
 await evaluate(`document.querySelector('[aria-label="Open driver menu"]').click()`);await wait(`document.querySelector('dialog').open`);await evaluate(`document.querySelector('dialog a[href="/driver/dashboard"]').click()`);await wait(`location.pathname==='/driver/dashboard' && !document.querySelector('dialog').open && document.body.innerText.includes('DR-BROWSER-ACCEPTED')`);
 await writeFile(path.join(out,'results.json'),JSON.stringify({responsive:results,workflow:'job details, acceptance, pickup, transit, cancel confirmation, complete, counts and history passed',mobileSidebar:true,keyboardFocus:true,loadingAndErrors:5,mutations},null,2));
 console.log(JSON.stringify({responsiveChecks:results.length,workflow:'passed',screenshots:out}));
 closing=true;await send('Browser.close').catch(error=>{if(error.message!=='Browser closed')throw error;});
}finally{closing=true;ws?.close();chrome.kill();await new Promise(resolve=>server.close(resolve));}
