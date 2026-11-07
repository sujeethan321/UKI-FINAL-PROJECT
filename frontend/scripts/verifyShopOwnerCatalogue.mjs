// Actual database browser QA. Run only with verified test-only backend on 8013
// and the temporary .server-logs/day14-catalogue-fixture.json (never committed).
// Prepare/clean it with backend/scripts/catalogue_browser_fixture.py.
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../../',import.meta.url)),out=path.join(root,'.server-logs','day14-catalogue-browser');await mkdir(out,{recursive:true});
const fixture=JSON.parse(await readFile(path.join(root,'.server-logs/day14-catalogue-fixture.json'),'utf8'));
assert.equal(fixture.database,'lankapex_test_db');assert.ok(fixture.ownerToken&&fixture.customerToken);
const server=createServer(async(req,res)=>{try{const name=new URL(req.url,'http://localhost').pathname;
 const file=path.join(root,'frontend/dist',name.startsWith('/assets/')?name:'/index.html'),data=await readFile(file);
 res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.png')?'image/png':'text/html');res.end(data);
}catch{res.writeHead(404);res.end();}});
await new Promise(resolve=>server.listen(5187,'127.0.0.1',resolve));
const chrome=spawn(process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',[
 '--headless=new','--no-first-run','--no-default-browser-check','--disable-gpu','--remote-debugging-port=9237','--remote-allow-origins=*','--user-data-dir='+path.join(out,'chrome-profile'),'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws,closing=false,activeToken=fixture.ownerToken;const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
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
   }
   await send('Fetch.fulfillRequest',{requestId:event.requestId,responseCode:status,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'http://127.0.0.1:5187'},{name:'Access-Control-Allow-Headers',value:'authorization,content-type'},{name:'Access-Control-Allow-Methods',value:'GET,POST,PATCH,OPTIONS'}],body:Buffer.from(body).toString('base64')});
  }catch(error){if(!closing&&!/Invalid InterceptionId/.test(error.message))throw error;}
 });
 await send('Page.enable');await send('Runtime.enable');await send('Page.bringToFront');
 await send('Fetch.enable',{patterns:[{urlPattern:'http://127.0.0.1:8000/*'},{urlPattern:'http://localhost:8000/*'}]});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:'if(!sessionStorage.getItem("lankapex_access_token"))sessionStorage.setItem("lankapex_access_token",'+JSON.stringify(fixture.ownerToken)+')'});

 const click=async label=>{await wait(`Array.from(document.querySelectorAll('button')).some(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`);return evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)});if(!b)throw Error('Missing button '+${JSON.stringify(label)});b.click();})()`);};
 const type=async(selector,value)=>{await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.focus();e.select();})()`);await send('Input.insertText',{text:value});};
 const navigate=async(token,route)=>{activeToken=token;await evaluate('sessionStorage.setItem("lankapex_access_token",'+JSON.stringify(token)+')');await send('Page.navigate',{url:'http://127.0.0.1:5187'+route});};
 const responsive=[];
 async function checkWidths(label){for(const width of [1536,1366,1024,768,375]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:false});await evaluate('scrollTo(0,0)');await delay(100);
  assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth && document.body.scrollWidth<=innerWidth'),'Overflow '+label+' '+width);
  assert.equal(await evaluate(`Array.from(document.querySelectorAll('p,h3')).filter(p=>p.textContent.startsWith('DR-')&&!p.children.length).some(p=>p.scrollWidth>p.clientWidth+1)`),false,'Clipped reference');
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
 const business=fixture.businesses[0];
 const customer=async()=>{const r=await testApi('/customer/catalogue/shops/'+business+'/products',{headers:{Authorization:'Bearer '+fixture.customerToken}});assert.equal(r.status,200);return r.json();};
 await send('Page.navigate',{url:'http://127.0.0.1:5187/shop-owner/products'});
 await wait(`document.body.innerText.includes('No products match these filters.') && document.body.innerText.includes('No categories yet.')`);await checkWidths('empty');
 assert.equal((await testApi('/shop-owner/catalogue/summary?business_id='+fixture.businesses[2])).status,404);
 await click('Add Category');await wait(`document.querySelector('#category-name')`);await type('#category-name','Retail essentials');await type('#category-description','Test catalogue category');await checkWidths('category-form');await click('Create Category');
 await wait(`!document.querySelector('#category-name') && document.body.innerText.includes('Retail essentials')`);
 let categories=await(await testApi('/shop-owner/categories?business_id='+business)).json();assert.equal(categories.total,1);const categoryId=categories.categories[0].category_id;
 await click('Add Product');await wait(`document.querySelector('#product-name')`);await type('#product-name','Rice sample');await type('#product-description','Plain test catalogue item');await type('#product-price','125.25');await choose('#product-category',categoryId);await checkWidths('add-product');await click('Create Product');
 await wait(`!document.querySelector('#product-name') && document.body.innerText.includes('Rice sample') && document.body.innerText.includes('LKR 125.25')`);await checkWidths('draft-product');assert.equal((await customer()).total,0);
 let products=await(await testApi('/shop-owner/products?business_id='+business)).json();assert.equal(products.total,1);const productId=products.products[0].product_id;
 await click('Edit Product');await wait(`document.querySelector('#product-price')?.value==='125.25'`);await type('#product-name','Premium rice sample');await type('#product-price','199.99');await checkWidths('edit-product');await click('Save Product');
 await wait(`!document.querySelector('#product-name') && document.body.innerText.includes('LKR 199.99')`);
 await click('Publish Product');await wait(`document.body.innerText.includes('Unpublish Product')`);assert.equal((await customer()).products[0].unit_price,'199.99');await checkWidths('published-product');
 await click('Mark Unavailable');await wait(`document.body.innerText.includes('Mark Available')`);assert.equal((await customer()).products[0].availability_status,'unavailable');
 await click('Unpublish Product');await wait(`document.body.innerText.includes('Publish Product')`);assert.equal((await customer()).total,0);
 await click('Publish Product');await wait(`document.body.innerText.includes('Unpublish Product')`);
 await click('Deactivate Category');await wait(`document.body.innerText.includes('Activate Category')`);assert.equal((await customer()).total,0);
 await click('Activate Category');await wait(`document.body.innerText.includes('Deactivate Category')`);assert.equal((await customer()).total,1);
 await click('Edit Category');await wait(`document.querySelector('#category-name')`);await type('#category-name','Essentials renamed');await click('Save Category');await wait(`!document.querySelector('#category-name') && document.body.innerText.includes('Category: Essentials renamed')`);
 await type('#catalogue-search','No matching product');await click('Search products');await wait(`document.body.innerText.includes('No products match these filters.')`);
 assert.equal(await evaluate(`document.querySelector('[aria-label="Catalogue summary"] article p')?.textContent`),'1');
 await type('#catalogue-search','rice');await click('Search products');await wait(`document.body.innerText.includes('Premium rice sample')`);
 await click('Archive Product');await wait(`document.body.innerText.includes('Confirm Archive')`);await checkWidths('archive-confirm');await click('Confirm Archive');await wait(`document.body.innerText.includes('Archived record. Changes are unavailable.')`);assert.equal((await customer()).total,0);await checkWidths('archived-product');
 await type('#catalogue-search','');await click('Search products');await wait(`document.body.innerText.includes('Archived record.')`);
 await click('Add Product');await wait(`document.querySelector('#product-name')`);await type('#product-name','Maximum price sample');await type('#product-price','9999999999.99');await click('Create Product');await wait(`!document.querySelector('#product-name') && document.body.innerText.includes('LKR 9,999,999,999.99')`);await checkWidths('maximum-price');
 await choose('#catalogue-business',fixture.businesses[1]);await wait(`document.body.innerText.includes('No products match these filters.') && document.body.innerText.includes('No categories yet.')`);assert.equal(await evaluate(`document.querySelector('[aria-label="Catalogue summary"] article p')?.textContent`),'0');await checkWidths('second-business');
 await choose('#catalogue-business',business);await wait(`document.body.innerText.includes('Maximum price sample')`);
 const summary=await(await testApi('/shop-owner/catalogue/summary?business_id='+business)).json();assert.deepEqual(summary,{business_id:business,total_products_count:2,available_products_count:1,categories_count:1,unpublished_products_count:1});
 products=await(await testApi('/shop-owner/products?business_id='+business)).json();assert.equal(products.total,2);assert.equal(products.products.find(p=>p.product_id===productId).publication_status,'archived');
 assert.equal((await customer()).total,0);
 await writeFile(path.join(out,'results.json'),JSON.stringify({database:'lankapex_test_db',responsive,summary,products:products.products,workflow:'passed'},null,2));
 console.log(JSON.stringify({responsiveChecks:responsive.length,accessibilityChecks:responsive.length,catalogueWorkflow:'passed',productsCreated:2,categoriesCreated:1}));
 closing=true;await send('Browser.close').catch(error=>{if(error.message!=='Browser closed')throw error;});
}finally{closing=true;ws?.close();chrome.kill();await new Promise(resolve=>server.close(resolve));}
