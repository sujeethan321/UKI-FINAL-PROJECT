// Actual database browser QA. Run only with verified test-only backend on 8013
// and the temporary .server-logs/day13-integration-fixture.json (never committed).
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../../',import.meta.url)),out=path.join(root,'.server-logs/day13-integration-browser');await mkdir(out,{recursive:true});
const fixture=JSON.parse(await readFile(path.join(root,'.server-logs/day13-integration-fixture.json'),'utf8'));
assert.equal(fixture.database,'lankapex_test_db');assert.ok(fixture.ownerToken&&fixture.driverToken);
const server=createServer(async(req,res)=>{try{const name=new URL(req.url,'http://localhost').pathname;
 const file=path.join(root,'frontend/dist',name.startsWith('/assets/')?name:'/index.html'),data=await readFile(file);
 res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.png')?'image/png':'text/html');res.end(data);
}catch{res.writeHead(404);res.end();}});
await new Promise(resolve=>server.listen(5187,'127.0.0.1',resolve));
const chrome=spawn(process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',[
 '--headless=new','--no-first-run','--no-default-browser-check','--disable-gpu','--remote-debugging-port=9237','--remote-allow-origins=*','--user-data-dir='+path.join(out,'chrome-profile'),'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws,closing=false,createdId,creates=0,cancels=0,activeToken=fixture.ownerToken;const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
 let page;for(let i=0;i<60;i++){try{page=await(await fetch('http://127.0.0.1:9237/json/new?about:blank',{method:'PUT'})).json();break;}catch{await delay(250);}}assert.ok(page);
 ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 let sequence=0;const pending=new Map(),handlers=new Map();
 const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>reject(Error('CDP timeout '+method)),15000);
  pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});ws.send(JSON.stringify({id,method,params}));});
 ws.onmessage=event=>{const msg=JSON.parse(event.data);if(msg.id){const task=pending.get(msg.id);pending.delete(msg.id);msg.error?task.reject(Error(JSON.stringify(msg.error))):task.resolve(msg.result);}else handlers.get(msg.method)?.(msg.params);};
 ws.onclose=()=>{for(const task of pending.values())task.reject(Error('Browser closed'));pending.clear();};
 const evaluate=async expression=>{const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;};
 const wait=async expression=>{for(let i=0;i<100;i++){try{if(await evaluate('Boolean(document.body)&&Boolean('+expression+')'))return;}catch(error){if(!/context|Context/.test(error.message))throw error;}await delay(100);}throw Error('Timed out '+expression+'\n'+await evaluate('document.body?.innerText'));};
 const testApi=async(endpoint,options={})=>fetch('http://127.0.0.1:8013/api/v1'+endpoint,{...options,headers:{Authorization:'Bearer '+fixture.ownerToken,'Content-Type':'application/json',...options.headers}});
 handlers.set('Fetch.requestPaused',async event=>{
  try{
   const source=new URL(event.request.url),endpoint=source.pathname+source.search;
   // Fulfill from the test-only backend; never continue requests to port 8000.
   let status=204,body='';
   if(event.request.method!=='OPTIONS'){
    const headers={'Content-Type':'application/json',Authorization:event.request.headers.Authorization||event.request.headers.authorization||'Bearer '+activeToken};
    const result=await fetch('http://127.0.0.1:8013'+endpoint,{method:event.request.method,headers,...(event.request.postData?{body:event.request.postData}:{})});status=result.status;body=await result.text();
    if(event.request.method==='POST'&&source.pathname==='/api/v1/shop-owner/deliveries'&&status===201){createdId=JSON.parse(body).delivery_request_id;creates++;}
    if(event.request.method==='POST'&&source.pathname.endsWith('/cancel')&&status===200)cancels++;
   }
   await send('Fetch.fulfillRequest',{requestId:event.requestId,responseCode:status,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'http://127.0.0.1:5187'},{name:'Access-Control-Allow-Headers',value:'authorization,content-type'},{name:'Access-Control-Allow-Methods',value:'GET,POST,OPTIONS'}],body:Buffer.from(body).toString('base64')});
  }catch(error){if(!closing)throw error;}
 });
 await send('Page.enable');await send('Runtime.enable');await send('Page.bringToFront');
 await send('Fetch.enable',{patterns:[{urlPattern:'http://127.0.0.1:8000/*'},{urlPattern:'http://localhost:8000/*'}]});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:'if(!sessionStorage.getItem("lankapex_access_token"))sessionStorage.setItem("lankapex_access_token",'+JSON.stringify(fixture.ownerToken)+')'});

 const click=label=>evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)});if(!b)throw Error('Missing button '+${JSON.stringify(label)});b.click();})()`);
 const type=async(selector,value)=>{await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`);await send('Input.insertText',{text:value});};
 const navigate=async(token,route)=>{activeToken=token;await evaluate('sessionStorage.setItem("lankapex_access_token",'+JSON.stringify(token)+')');await send('Page.navigate',{url:'http://127.0.0.1:5187'+route});};
 const responsive=[];
 async function checkWidths(label){for(const width of [1536,1366,1024,768,375]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:false});await evaluate('scrollTo(0,0)');await delay(100);
  assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth && document.body.scrollWidth<=innerWidth'),'Overflow '+label+' '+width);
  assert.equal(await evaluate(`Array.from(document.querySelectorAll('p,h3')).filter(p=>p.textContent.startsWith('DR-')&&!p.children.length).some(p=>p.scrollWidth>p.clientWidth+1)`),false,'Clipped reference');
  const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await writeFile(path.join(out,label+'-'+width+'.png'),Buffer.from(shot.data,'base64'));responsive.push({label,width,overflow:false,clippedReference:false});
 }}
 await send('Page.navigate',{url:'http://127.0.0.1:5187/shop-owner/deliveries'});await wait(`document.body.innerText.includes('No delivery requests match this filter')`);
 await type('#delivery-pickup','Integration pickup district');await type('#delivery-destination','Integration destination district');await click('Create Delivery Request');
 await wait(`document.body.innerText.includes('Delivery request created.') && document.body.innerText.includes('Cancel Request')`);assert.equal(creates,1);assert.ok(createdId);
 const original=await(await testApi('/shop-owner/deliveries/'+createdId+'?business_id='+fixture.businessId)).json();const reference=original.reference;
 await checkWidths('owner-created');
 let response=await testApi('/driver/jobs/'+createdId+'/accept',{method:'POST',body:'{}',headers:{Authorization:'Bearer '+fixture.pendingToken}});assert.equal(response.status,403);
 response=await testApi('/driver/jobs',{headers:{Authorization:'Bearer '+fixture.driverBToken}});assert.ok((await response.json()).jobs.some(job=>job.delivery_request_id===createdId));
 await navigate(fixture.driverToken,'/driver/jobs');await wait(`document.body.innerText.includes(${JSON.stringify(reference)}) && document.body.innerText.includes('Accept Job')`);await checkWidths('driver-jobs');
 await click('Accept Job');await wait(`document.body.innerText.includes('Assignment confirmed') && document.body.innerText.includes('No available delivery jobs right now.')`);
 response=await testApi('/driver/jobs/'+createdId+'/accept',{method:'POST',body:'{}',headers:{Authorization:'Bearer '+fixture.driverBToken}});assert.equal(response.status,409);
 response=await testApi('/driver/deliveries/'+createdId,{headers:{Authorization:'Bearer '+fixture.driverBToken}});assert.equal(response.status,404);
 await navigate(fixture.driverToken,'/driver/dashboard');await wait(`document.body.innerText.includes(${JSON.stringify(reference)})`);await checkWidths('driver-dashboard');
 await navigate(fixture.driverToken,'/driver/deliveries');await wait(`document.body.innerText.includes(${JSON.stringify(reference)})`);await checkWidths('driver-assigned');
 async function ownerStatus(status,label){
  await navigate(fixture.ownerToken,'/shop-owner/deliveries');await wait(`document.body.innerText.includes(${JSON.stringify(reference)}) && document.body.innerText.includes('View Details')`);await click('View Details');
  await wait(`document.querySelector('[aria-labelledby="shop-delivery-detail-heading"] span')?.textContent.trim()===${JSON.stringify(label)}`);
  assert.ok(await evaluate(`document.body.innerText.includes('Integration Driver A')`));
  assert.equal(await evaluate(`Array.from(document.querySelectorAll('button')).some(b=>b.textContent.trim()==='Cancel Request')`),false);
  const result=await(await testApi('/shop-owner/deliveries/'+createdId+'?business_id='+fixture.businessId)).json();assert.equal(result.status,status);return result;
 }
 await ownerStatus('assigned','Assigned');
 await navigate(fixture.driverToken,'/driver/deliveries/'+createdId);await wait(`document.body.innerText.includes('Confirm Pickup')`);await checkWidths('driver-details');
 const ownerEvents=[];
 for(const [button,status,label,nextButton] of [['Confirm Pickup','picked_up','Picked up','Start Delivery'],['Start Delivery','in_transit','In transit','Mark Delivered'],['Mark Delivered','delivered','Completed',null]]){
  if(button==='Mark Delivered'){await click(button);await wait(`document.body.innerText.includes('Confirm Delivered')`);await click('Confirm Delivered');await wait(`document.body.innerText.includes('No further status updates')`);}
  else{await click(button);await wait(`document.body.innerText.includes(${JSON.stringify(nextButton)})`);}
  const owner=await ownerStatus(status,label);ownerEvents.push(owner.events);
  const driver=await(await testApi('/driver/deliveries/'+createdId,{headers:{Authorization:'Bearer '+fixture.driverToken}})).json();assert.deepEqual(owner.events,driver.events);
  if(nextButton){await navigate(fixture.driverToken,'/driver/deliveries/'+createdId);await wait(`document.body.innerText.includes(${JSON.stringify(nextButton)})`);}
 }
 await checkWidths('owner-completed');
 await navigate(fixture.driverToken,'/driver/history');await wait(`document.body.innerText.includes(${JSON.stringify(reference)})`);await checkWidths('driver-history');
 await navigate(fixture.driverToken,'/driver/dashboard');await wait(`document.body.innerText.includes('No active deliveries yet.') && Array.from(document.querySelectorAll('article')).some(a=>a.innerText.includes('Completed Deliveries') && a.querySelector('p')?.textContent==='1')`);
 const ownerCounts=await(await testApi('/shop-owner/deliveries/summary?business_id='+fixture.businessId)).json();assert.equal(ownerCounts.total_requests_count,1);assert.equal(ownerCounts.completed_count,1);assert.equal(ownerCounts.in_progress_count,0);
 const driverCounts=await(await testApi('/driver/dashboard/summary',{headers:{Authorization:'Bearer '+fixture.driverToken}})).json();assert.equal(driverCounts.completed_deliveries_count,1);assert.equal(driverCounts.active_deliveries_count,0);
 assert.deepEqual(ownerEvents.at(-1).map(event=>event.status),['assigned','picked_up','in_transit','delivered']);assert.equal(creates,1);assert.equal(cancels,0);
 await writeFile(path.join(out,'results.json'),JSON.stringify({database:'lankapex_test_db',responsive,creates,cancels,requestId:createdId,reference,ownerCounts,driverCounts,events:ownerEvents.at(-1),workflow:'passed'},null,2));
 console.log(JSON.stringify({responsiveChecks:responsive.length,realCrossRoleJourney:'passed',creates,progressStages:3}));
 closing=true;await send('Browser.close').catch(error=>{if(error.message!=='Browser closed')throw error;});
}finally{closing=true;ws?.close();chrome.kill();await new Promise(resolve=>server.close(resolve));}
