// Actual database browser QA. Run only with verified test-only backend on 8013
// and the temporary .server-logs/day14-catalogue-fixture.json (never committed).
// Prepare/clean it with backend/scripts/catalogue_browser_fixture.py.
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../../',import.meta.url)),out=path.join(root,'.server-logs','day14-customer-browser');await mkdir(out,{recursive:true});
const fixture=JSON.parse(await readFile(path.join(root,'.server-logs/day14-catalogue-fixture.json'),'utf8'));
assert.equal(fixture.database,'lankapex_test_db');assert.ok(fixture.ownerToken&&fixture.customerToken);
const server=createServer(async(req,res)=>{try{const name=new URL(req.url,'http://localhost').pathname;
 const file=path.join(root,'frontend/dist',name.startsWith('/assets/')?name:'/index.html'),data=await readFile(file);
 res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.png')?'image/png':'text/html');res.end(data);
}catch{res.writeHead(404);res.end();}});
await new Promise(resolve=>server.listen(5187,'127.0.0.1',resolve));
const chrome=spawn(process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',[
 '--headless=new','--no-first-run','--no-default-browser-check','--disable-gpu','--remote-debugging-port=9237','--remote-allow-origins=*','--user-data-dir='+path.join(out,'chrome-profile'),'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws,closing=false,activeToken=fixture.customerToken;const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
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
   const source=new URL(event.request.url),endpoint=source.pathname+source.search;browserMethods.push(event.request.method);
   // Fulfill from the test-only backend; never continue requests to port 8000.
   let status=204,body='';
   if(event.request.method!=='OPTIONS'){
    const headers={'Content-Type':'application/json',Authorization:event.request.headers.Authorization||event.request.headers.authorization||'Bearer '+activeToken};
    const result=await fetch('http://127.0.0.1:8013'+endpoint,{method:event.request.method,headers,...(event.request.postData?{body:event.request.postData}:{})});status=result.status;body=await result.text();
   }
   await send('Fetch.fulfillRequest',{requestId:event.requestId,responseCode:status,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'http://127.0.0.1:5187'},{name:'Access-Control-Allow-Headers',value:'authorization,content-type'},{name:'Access-Control-Allow-Methods',value:'GET,POST,PATCH,OPTIONS'}],body:Buffer.from(body).toString('base64')});
  }catch(error){if(!closing&&!/Invalid InterceptionId/.test(error.message))throw error;}
 });
 await send('Page.enable');await send('Runtime.enable');await send('Page.bringToFront');
 await send('Fetch.enable',{patterns:[{urlPattern:'http://127.0.0.1:8000/*'},{urlPattern:'http://localhost:8000/*'}]});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:'if(!sessionStorage.getItem("lankapex_access_token"))sessionStorage.setItem("lankapex_access_token",'+JSON.stringify(fixture.customerToken)+')'});

 const click=async label=>{await wait(`Array.from(document.querySelectorAll('button')).some(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`);return evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)});if(!b)throw Error('Missing button '+${JSON.stringify(label)});b.click();})()`);};
 const type=async(selector,value)=>{await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.focus();e.select();})()`);await send('Input.insertText',{text:value});};
 const navigate=async(token,route)=>{activeToken=token;await evaluate('sessionStorage.setItem("lankapex_access_token",'+JSON.stringify(token)+')');await send('Page.navigate',{url:'http://127.0.0.1:5187'+route});};
 const responsive=[],browserMethods=[];
 async function checkWidths(label){for(const width of [1536,1366,1024,768,375]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:false});await evaluate('scrollTo(0,0)');await delay(100);
  assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth && document.body.scrollWidth<=innerWidth'),'Overflow '+label+' '+width);
  assert.equal(await evaluate(`Array.from(document.querySelectorAll('main h3')).some(p=>p.scrollWidth>p.clientWidth+1)`),false,'Clipped reference');
  const accessibility=await evaluate(`(()=>{
    const visible=e=>!!e.getClientRects().length;
    const fields=[...document.querySelectorAll('main input,main select,main textarea')].filter(visible);
    const buttons=[...document.querySelectorAll('main button')].filter(visible);
    const overlaps=[];
    for(let i=0;i<buttons.length;i++)for(let j=i+1;j<buttons.length;j++){
      const a=buttons[i].getBoundingClientRect(),b=buttons[j].getBoundingClientRect();
      if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)overlaps.push([buttons[i].textContent,buttons[j].textContent]);
    }
    return {unlabelled:fields.filter(e=>!e.labels?.length&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')).length,
      unnamedButtons:buttons.filter(e=>!e.textContent.trim()&&!e.getAttribute('aria-label')).length,overlaps};
  })()`);
  assert.equal(accessibility.unlabelled,0,'Form labels '+label+' '+width);
  assert.equal(accessibility.unnamedButtons,0,'Action labels '+label+' '+width);
  assert.deepEqual(accessibility.overlaps,[],'Overlapping actions '+label+' '+width);
  await evaluate(`document.querySelector('main button:not([disabled])')?.focus()`);
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  assert.ok(await evaluate(`(()=>{const e=document.activeElement,s=getComputedStyle(e);return e!==document.body&&e.matches(':focus-visible')&&((s.outlineStyle!=='none'&&parseFloat(s.outlineWidth)>0)||s.boxShadow!=='none');})()`),'Keyboard focus '+label+' '+width);
  if(width<1024){
    await evaluate('scrollTo(0,Math.min(250,document.documentElement.scrollHeight-innerHeight))');await delay(100);
    const mobileMenu=await evaluate(`(()=>{const menu=document.querySelector('[aria-label="Open customer menu"], [aria-label="Open shop owner menu"]'),header=document.querySelector('header');if(!menu||!header)return null;const m=menu.getBoundingClientRect(),h=header.getBoundingClientRect();return {contained:m.top>=h.top&&m.bottom<=h.bottom,scrollY};})()`);
    assert.ok(mobileMenu?.contained,'Mobile menu must remain inside its header while scrolling '+label+' '+width);
    await evaluate('scrollTo(0,0)');
  }
  const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await writeFile(path.join(out,label+'-'+width+'.png'),Buffer.from(shot.data,'base64'));responsive.push({label,width,overflow:false,clippedReference:false});
 }}
 const choose=(selector,value)=>evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.value=${JSON.stringify(String(value))};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 const business=fixture.businesses[0],foreign=fixture.businesses[2];
 async function ownerWrite(path,payload,token=fixture.ownerToken,method='POST'){
  const response=await testApi(path,{method,body:JSON.stringify(payload),headers:{Authorization:'Bearer '+token}});assert.ok(response.ok,await response.clone().text());return response.json();
 }
 const category=await ownerWrite('/shop-owner/categories?business_id='+business,{name:'Retail essentials'});
 const add=(payload)=>ownerWrite('/shop-owner/products?business_id='+business,{name:'Sample',unit_price:'1.00',...payload});
 const available=await add({name:'Maximum price sample',description:'Published retail sample',unit_price:'9999999999.99',category_id:category.category_id,publication_status:'published'});
 const unavailable=await add({name:'Unavailable sample',unit_price:'199.99',category_id:category.category_id,publication_status:'published',availability_status:'unavailable'});
 const draft=await add({name:'DRAFT-HIDDEN'});
 const archived=await add({name:'ARCHIVE-HIDDEN'});await ownerWrite('/shop-owner/products/'+archived.product_id+'?business_id='+business,{publication_status:'archived'},fixture.ownerToken,'PATCH');
 const inactive=await ownerWrite('/shop-owner/categories?business_id='+business,{name:'Inactive category'});
 await add({name:'INACTIVE-HIDDEN',category_id:inactive.category_id,publication_status:'published'});await ownerWrite('/shop-owner/categories/'+inactive.category_id+'?business_id='+business,{is_active:false},fixture.ownerToken,'PATCH');
 await ownerWrite('/shop-owner/products?business_id='+foreign,{name:'Other shop rice',unit_price:'15.00',publication_status:'published'},fixture.foreignToken);
 assert.equal((await testApi('/shop-owner/products?business_id='+business,{headers:{Authorization:'Bearer '+fixture.customerToken}})).status,403);
 await send('Page.navigate',{url:'http://127.0.0.1:5187/customer/shops/explore'});await wait(`document.querySelectorAll('[aria-label="Eligible shops"] article').length===2`);await checkWidths('explore');
 await type('#shop-search','No such catalogue');await click('Search shops');await wait(`document.body.innerText.includes('No shops match your search.')`);await checkWidths('shop-search-empty');
 await type('#shop-search','browser 0');await click('Search shops');await wait(`document.querySelectorAll('[aria-label="Eligible shops"] article').length===1`);await checkWidths('shop-search');
 await evaluate(`document.querySelector('main a[href="/customer/explore/${business}"]').click()`);await wait(`document.querySelectorAll('[aria-label="Published products"] article').length===2`);
 for(const name of ['DRAFT-HIDDEN','ARCHIVE-HIDDEN','INACTIVE-HIDDEN','Other shop rice'])assert.equal(await evaluate('document.body.innerText.includes('+JSON.stringify(name)+')'),false);
 await checkWidths('shop-catalogue');
 await type('#product-search','Maximum');await click('Search products');await wait(`document.querySelectorAll('[aria-label="Published products"] article').length===1`);assert.ok(await evaluate(`document.body.innerText.includes('LKR 9,999,999,999.99')`));
 await type('#product-search','');await click('Search products');await wait(`document.querySelectorAll('[aria-label="Published products"] article').length===2`);
 await choose('#browse-category',category.category_id);await choose('#browse-availability','unavailable');await wait(`document.querySelectorAll('[aria-label="Published products"] article').length===1 && document.body.innerText.includes('Unavailable sample')`);await checkWidths('unavailable-filter');
 await evaluate(`document.querySelector('main a[href="/customer/explore/${business}/products/${unavailable.product_id}"]').click()`);await wait(`document.body.innerText.includes('currently marked unavailable')`);await checkWidths('unavailable-product');
 await navigate(fixture.customerToken,'/customer/explore/'+business+'/products/'+available.product_id);await wait(`document.body.innerText.includes('Published retail sample')`);assert.ok(await evaluate(`document.body.innerText.includes('LKR 9,999,999,999.99')`));await checkWidths('product-details');
 await navigate(fixture.customerToken,'/customer/explore/'+business+'/products/'+draft.product_id);await wait(`document.body.innerText.includes('This shop or product is no longer available.')`);assert.equal(await evaluate(`document.body.innerText.includes('DRAFT-HIDDEN')`),false);await checkWidths('hidden-product');
 await navigate(fixture.customerToken,'/customer/explore/999999999');await wait(`document.body.innerText.includes('This shop or product is no longer available.')`);await checkWidths('unavailable-shop');
 await navigate(fixture.customerToken,'/customer/explore/'+fixture.businesses[1]);await wait(`document.body.innerText.includes('This shop has no published products currently.')`);await checkWidths('empty-shop');
 await send('Emulation.setDeviceMetricsOverride',{width:375,height:1100,deviceScaleFactor:1,mobile:false});
 await evaluate(`document.querySelector('[aria-label="Open customer menu"]').click()`);await wait(`document.querySelector('#customer-mobile-sidebar').open`);
 await evaluate(`document.querySelector('#customer-mobile-sidebar a[href="/customer/shops"]').click()`);await wait(`location.pathname==='/customer/shops' && !document.querySelector('#customer-mobile-sidebar').open`);
 assert.equal(await evaluate(`document.body.innerText.includes('Maximum price sample')`),false);
 await navigate(fixture.customerToken,'/customer/shops/explore');await wait(`document.querySelectorAll('[aria-label="Eligible shops"] article').length===2`);
 assert.ok(browserMethods.every(method=>['GET','OPTIONS'].includes(method)),'Customer browsing must be read-only');
 assert.equal(await evaluate(`Array.from(document.querySelectorAll('button,a')).some(e=>/Add to Cart|Buy Now/.test(e.textContent))`),false);
 await writeFile(path.join(out,'results.json'),JSON.stringify({database:'lankapex_test_db',responsive,browserMethods,workflow:'passed',mobileNavigation:'passed',publicProducts:2},null,2));
 console.log(JSON.stringify({responsiveChecks:responsive.length,accessibilityChecks:responsive.length,customerBrowsing:'passed',readOnlyRequests:true,mobileNavigation:'passed'}));
 closing=true;await send('Browser.close').catch(error=>{if(error.message!=='Browser closed')throw error;});
}finally{closing=true;ws?.close();chrome.kill();await new Promise(resolve=>server.close(resolve));}
