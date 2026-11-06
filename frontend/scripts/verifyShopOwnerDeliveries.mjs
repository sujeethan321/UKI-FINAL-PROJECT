// Actual database browser QA. Run only with verified test-only backend on 8013
// and the temporary .server-logs/day13-ui-fixture.json (never committed).
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../../',import.meta.url)),out=path.join(root,'.server-logs/day13-ui-browser');await mkdir(out,{recursive:true});
const fixture=JSON.parse(await readFile(path.join(root,'.server-logs/day13-ui-fixture.json'),'utf8'));
assert.equal(fixture.database,'lankapex_test_db');assert.ok(fixture.ownerToken&&fixture.driverToken);
const server=createServer(async(req,res)=>{try{const name=new URL(req.url,'http://localhost').pathname;
 const file=path.join(root,'frontend/dist',name.startsWith('/assets/')?name:'/index.html'),data=await readFile(file);
 res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.png')?'image/png':'text/html');res.end(data);
}catch{res.writeHead(404);res.end();}});
await new Promise(resolve=>server.listen(5187,'127.0.0.1',resolve));
const chrome=spawn(process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',[
 '--headless=new','--no-first-run','--no-default-browser-check','--disable-gpu','--remote-debugging-port=9237','--remote-allow-origins=*','--user-data-dir='+path.join(out,'chrome-profile'),'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws,closing=false,createdId,creates=0,cancels=0;const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
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
    const headers={'Content-Type':'application/json',Authorization:event.request.headers.Authorization||event.request.headers.authorization||'Bearer '+fixture.ownerToken};
    const result=await fetch('http://127.0.0.1:8013'+endpoint,{method:event.request.method,headers,...(event.request.postData?{body:event.request.postData}:{})});status=result.status;body=await result.text();
    if(event.request.method==='POST'&&source.pathname==='/api/v1/shop-owner/deliveries'&&status===201){createdId=JSON.parse(body).delivery_request_id;creates++;}
    if(event.request.method==='POST'&&source.pathname.endsWith('/cancel')&&status===200)cancels++;
   }
   await send('Fetch.fulfillRequest',{requestId:event.requestId,responseCode:status,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'http://127.0.0.1:5187'},{name:'Access-Control-Allow-Headers',value:'authorization,content-type'},{name:'Access-Control-Allow-Methods',value:'GET,POST,OPTIONS'}],body:Buffer.from(body).toString('base64')});
  }catch(error){if(!closing)throw error;}
 });
 await send('Page.enable');await send('Runtime.enable');await send('Page.bringToFront');
 await send('Fetch.enable',{patterns:[{urlPattern:'http://127.0.0.1:8000/*'},{urlPattern:'http://localhost:8000/*'}]});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:'sessionStorage.setItem("lankapex_access_token",'+JSON.stringify(fixture.ownerToken)+')'});
 await send('Page.navigate',{url:'http://127.0.0.1:5187/shop-owner/deliveries'});await wait(`document.body.innerText.includes('No delivery requests match this filter')`);
 const click=label=>evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)});if(!b)throw Error('Missing button');b.click();})()`);
 const type=async(selector,value)=>{await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`);await send('Input.insertText',{text:value});};
 await type('#delivery-pickup','Browser pickup district');await type('#delivery-destination','Browser destination district');await click('Create Delivery Request');
 await wait(`document.body.innerText.includes('Delivery request created.')`);assert.equal(creates,1);assert.ok(createdId);
 await wait(`document.body.innerText.includes('Delivery Request Details') && document.body.innerText.includes('Cancel Request')`);
 const responsive=[];
 for(const width of [1536,1366,1024,768,375]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:false});await delay(150);
  assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth && document.body.scrollWidth<=innerWidth'),'Overflow '+width);
  assert.equal(await evaluate(`Array.from(document.querySelectorAll('p')).filter(p=>p.textContent.startsWith('DR-')).some(p=>p.scrollWidth>p.clientWidth+1)`),false,'Clipped reference '+width);
  assert.ok(await evaluate(`Boolean(document.querySelector('label[for="delivery-pickup"]')) && Boolean(document.querySelector('label[for="delivery-destination"]'))`));
  const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await writeFile(path.join(out,width+'.png'),Buffer.from(shot.data,'base64'));responsive.push({width,overflow:false,clippedReference:false});
 }
 await click('Cancel Request');await wait(`document.body.innerText.includes('Cancel this unassigned delivery request?')`);assert.equal(cancels,0);
 await click('Keep Request');assert.equal(cancels,0);await click('Cancel Request');await click('Confirm Cancellation');await wait(`document.body.innerText.includes('Delivery request cancelled.')`);assert.equal(cancels,1);
 let response=await testApi('/shop-owner/deliveries/'+createdId+'?business_id='+fixture.businessId);assert.equal(response.status,200);assert.equal((await response.json()).status,'cancelled');
 await type('#delivery-pickup','Second pickup district');await type('#delivery-destination','Second destination district');await click('Create Delivery Request');await wait(`document.body.innerText.includes('Delivery request created.')`);assert.equal(creates,2);
 response=await testApi('/driver/jobs/'+createdId+'/accept',{method:'POST',body:'{}',headers:{Authorization:'Bearer '+fixture.driverToken}});assert.equal(response.status,200);
 await click('Refresh deliveries');await wait(`document.body.innerText.includes('Browser QA driver')`);assert.ok(!await evaluate(`Array.from(document.querySelectorAll('button')).some(b=>b.textContent.trim()==='Cancel Request')`));
 response=await testApi('/shop-owner/deliveries/summary?business_id='+fixture.businessId);const summary=await response.json();assert.equal(summary.total_requests_count,2);assert.equal(summary.available_requests_count,0);assert.equal(summary.in_progress_count,1);
 await evaluate(`document.querySelector('#shop-delivery-status').value='cancelled';document.querySelector('#shop-delivery-status').dispatchEvent(new Event('change',{bubbles:true}))`);
 await wait(`document.querySelector('#shop-delivery-status').value==='cancelled' && !document.body.innerText.includes('Loading delivery requests...')`);
 await evaluate(`document.querySelector('[aria-label="Open shop owner menu"]').click()`);await wait(`document.querySelector('[aria-label="Close shop owner menu"]')`);
 await evaluate(`document.querySelector('[aria-label="Close shop owner menu"]').click()`);await wait(`!document.querySelector('[aria-label="Close shop owner menu"]')`);
 await evaluate(`document.querySelector('#delivery-pickup').focus()`);assert.ok(await evaluate(`getComputedStyle(document.activeElement).borderColor==='rgb(18, 184, 166)'`));
 await writeFile(path.join(out,'results.json'),JSON.stringify({database:'lankapex_test_db',responsive,creates,cancels,driverAssignment:true,summary,mobileSidebar:true,workflow:'passed'},null,2));
 console.log(JSON.stringify({responsiveChecks:responsive.length,realDatabaseWorkflow:'passed',creates,cancels}));
 closing=true;await send('Browser.close').catch(error=>{if(error.message!=='Browser closed')throw error;});
}finally{closing=true;ws?.close();chrome.kill();await new Promise(resolve=>server.close(resolve));}
