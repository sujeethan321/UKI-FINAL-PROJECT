// Preparation is offline by default. Only the exact execution gate opens Chrome.
import { readFile, mkdir, lstat, writeFile } from 'node:fs/promises';
import { spawn, execFile } from 'node:child_process';
import { createConnection } from 'node:net';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { ORIGIN, OUTPUT, CASES, ROLES, LANGUAGES, WIDTHS, MENU, identity, classify, executionGate, validateIdentityResponses, mockResponse } from './fourRoleMockPolicy.mjs';

const root = fileURLToPath(new URL('../../', import.meta.url));
const debugOrigin = 'http://127.0.0.1:9241';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const ensure = (condition, stage) => { if (!condition) throw Error(stage); };
const json = JSON.stringify;
// Only reviewed constants reach the console; exception text is never printed.
const phases = {
  confirmation: 'confirmation_mismatch',
  frontend_preflight: 'frontend_unexpected_failure',
  debugging_port: 'debugging_port_unverified',
  chrome_availability: 'chrome_unavailable',
  translation_catalog: 'translation_catalog_failure',
  output_creation: 'output_creation_failure',
  chrome_startup: 'chrome_startup_failure',
  network_setup: 'network_isolation_failure',
  browser_assertions: 'browser_assertion_failure',
  result_write: 'output_write_failure',
};
const categories = {
  confirmation: 'confirmation_mismatch', frontend_identity: 'frontend_identity_mismatch',
  source_map: 'source_map_mismatch', frontend_configuration: 'api_configuration_mismatch',
  debug_port_busy: 'debugging_port_occupied', debug_port_unverified: 'debugging_port_unverified',
  chrome_missing: 'chrome_unavailable', browser_start: 'chrome_startup_failure',
  network_policy: 'network_isolation_failure', unexpected_network: 'network_isolation_failure',
  unexpected_api: 'network_isolation_failure', unexpected_target: 'network_isolation_failure',
};
const frontendCategories = new Set([
  'frontend_connection_failure', 'frontend_request_timeout', 'frontend_http_status_failure',
  'frontend_response_read_failure', 'frontend_response_too_large', 'frontend_transport_target_failure',
  'frontend_local_source_unavailable', 'frontend_unexpected_failure',
]);
const resourceLabels = new Set(['frontend_origin', 'main_jsx', 'app_jsx', 'api_js']);
const startupCategories = new Set(['chrome_spawn_failure', 'chrome_premature_exit',
  'devtools_discovery_timeout', 'devtools_discovery_malformed', 'devtools_identity_mismatch',
  'devtools_websocket_failure', 'devtools_websocket_timeout', 'devtools_owner_mismatch',
  'devtools_owner_ambiguous', 'devtools_owner_unavailable']);
const startupCodes = new Set(['EACCES', 'EPERM', 'ENOENT', 'ENOEXEC', 'ENOMEM', 'EAGAIN', 'EINVAL']);
const identityAssertions = new Set(['initial_tab_count', 'initial_tab_url', 'websocket_host', 'websocket_port', 'websocket_protocol']);
export function initialTabCountCategory(count) {
  if (!Number.isSafeInteger(count) || count < 0) return 'unknown';
  return count === 0 ? 'zero' : count === 2 ? 'two' : count >= 3 ? 'three_or_more' : 'unknown';
}
const boundedCount = count => count === 1 ? 'one' : initialTabCountCategory(count);
export function targetTypeCounts(targets) {
  if (!Array.isArray(targets)) return { page: 'unknown', nonPage: 'unknown', unknown: 'unknown' };
  let page = 0, nonPage = 0, unknown = 0;
  for (const target of targets) {
    if (target?.type === 'page') page++;
    else if (typeof target?.type === 'string' && target.type.trim()) nonPage++;
    else unknown++;
  }
  return { page: boundedCount(page), nonPage: boundedCount(nonPage), unknown: boundedCount(unknown) };
}
const runOwnershipMetadata = (file, args, options) => new Promise((resolve, reject) => {
  execFile(file, args, options, (error, stdout) => error ? reject(error) : resolve(stdout));
});
export async function verifyListenerOwnership(chrome, run = runOwnershipMetadata, platform = process.platform) {
  const alive = () => Number.isSafeInteger(chrome.pid) && chrome.pid > 0 && chrome.exitCode === null && chrome.signalCode == null;
  if (platform !== 'win32' || !alive()) throw new StartupFailure('devtools_owner_unavailable');
  // Kernel listener metadata must identify the directly tracked child. Descendants
  // are deliberately not inferred from an unverified parent-PID chain.
  const command = `$ErrorActionPreference='Stop'; try { $rows=@(Get-NetTCPConnection -State Listen -LocalPort 9241 -ErrorAction Stop); if($rows.Count -ne 1){'ambiguous'} elseif($rows[0].LocalAddress -ne '127.0.0.1'){'mismatch'} elseif($rows[0].OwningProcess -ne ${chrome.pid}){'mismatch'} else {'matched'} } catch {'unavailable'}`;
  let result;
  try {
    result = await run('C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
      ['-NoProfile', '-NonInteractive', '-Command', command],
      { windowsHide: true, timeout: 5000, maxBuffer: 1024, encoding: 'utf8' });
  } catch { throw new StartupFailure('devtools_owner_unavailable'); }
  if (!alive()) throw new StartupFailure('devtools_owner_unavailable');
  const status = typeof result === 'string' ? result.trim() : '';
  if (status === 'matched') return;
  throw new StartupFailure(status === 'mismatch' ? 'devtools_owner_mismatch'
    : status === 'ambiguous' ? 'devtools_owner_ambiguous' : 'devtools_owner_unavailable');
}
class StartupFailure extends Error {
  constructor(category, code, exitStatus, assertion, tabCount, targets) {
    super('startup_failure');
    this.category = startupCategories.has(category) ? category : 'chrome_startup_failure';
    this.code = startupCodes.has(code) ? code : undefined;
    this.exitStatus = Number.isSafeInteger(exitStatus) ? exitStatus : undefined;
    this.assertion = category === 'devtools_identity_mismatch' && identityAssertions.has(assertion) ? assertion : undefined;
    this.countCategory = this.assertion === 'initial_tab_count' ? initialTabCountCategory(tabCount) : undefined;
    this.targetCounts = this.assertion === 'initial_tab_count' ? targetTypeCounts(targets) : undefined;
  }
}
export function spawnChrome(file, args, options, start = spawn) {
  let chrome, failure;
  try { chrome = start(file, args, options); }
  catch (error) { throw new StartupFailure('chrome_spawn_failure', error?.code); }
  chrome.on('error', error => { failure = new StartupFailure('chrome_spawn_failure', error?.code); });
  return { chrome, spawnFailure: () => failure };
}
export async function discoverDevtools(chrome, spawnFailure, get = localGet, sleep = pause) {
  const checkProcess = () => {
    if (spawnFailure()) throw spawnFailure();
    if (chrome.exitCode !== null || chrome.signalCode != null) throw new StartupFailure('chrome_premature_exit', undefined, chrome.exitCode);
  };
  // Preserve bounded readiness polling; never relaunch Chrome or retry scenarios.
  for (let i = 0; i < 40; i++) {
    checkProcess();
    let body;
    try { body = await get(debugOrigin + '/json/list'); }
    catch (error) { if (error instanceof StartupFailure) throw error; checkProcess(); await sleep(150); continue; }
    checkProcess();
    let tabs;
    try { tabs = JSON.parse(body); }
    catch { throw new StartupFailure('devtools_discovery_malformed'); }
    if (!Array.isArray(tabs) || tabs.some(tab => !tab || typeof tab !== 'object' || typeof tab.url !== 'string' || typeof tab.webSocketDebuggerUrl !== 'string')) throw new StartupFailure('devtools_discovery_malformed');
    if (tabs.length !== 1) throw new StartupFailure('devtools_identity_mismatch', undefined, undefined, 'initial_tab_count', tabs.length, tabs);
    if (tabs[0].url !== 'about:blank') throw new StartupFailure('devtools_identity_mismatch', undefined, undefined, 'initial_tab_url');
    let socketUrl;
    try { socketUrl = new URL(tabs[0].webSocketDebuggerUrl); }
    catch { throw new StartupFailure('devtools_discovery_malformed'); }
    if (socketUrl.hostname !== '127.0.0.1') throw new StartupFailure('devtools_identity_mismatch', undefined, undefined, 'websocket_host');
    if (socketUrl.port !== '9241') throw new StartupFailure('devtools_identity_mismatch', undefined, undefined, 'websocket_port');
    if (socketUrl.protocol !== 'ws:') throw new StartupFailure('devtools_identity_mismatch', undefined, undefined, 'websocket_protocol');
    return socketUrl;
  }
  checkProcess();
  throw new StartupFailure('devtools_discovery_timeout');
}
export async function connectDevtools(socketUrl, onSocket, makeSocket = url => new WebSocket(url), schedule = setTimeout, cancel = clearTimeout) {
  let socket;
  try { socket = makeSocket(socketUrl); }
  catch { throw new StartupFailure('devtools_websocket_failure'); }
  onSocket(socket); // Retain the existing finally-block ownership of this socket.
  await new Promise((resolve, reject) => {
    const timeout = schedule(() => reject(new StartupFailure('devtools_websocket_timeout')), 5000);
    socket.onopen = () => { cancel(timeout); resolve(); };
    socket.onerror = socket.onclose = () => { cancel(timeout); reject(new StartupFailure('devtools_websocket_failure')); };
  });
}
class FrontendFailure extends Error {
  constructor(category, resource) {
    super('frontend_failure');
    this.category = frontendCategories.has(category) ? category : 'frontend_unexpected_failure';
    this.resource = resourceLabels.has(resource) ? resource : 'frontend_origin';
  }
}
export async function runWithDiagnostics(run, report = message => console.error(message)) {
  let stage = 'confirmation';
  const setStage = value => { ensure(Object.hasOwn(phases, value), 'diagnostic_stage'); stage = value; };
  try { await run(setStage); return true; }
  catch (error) {
    const category = error instanceof StartupFailure || error instanceof FrontendFailure ? error.category : error instanceof Error && Object.hasOwn(categories, error.message)
      ? categories[error.message] : phases[stage];
    const resource = error instanceof FrontendFailure ? ` resource=${error.resource}` : '';
    const startup = error instanceof StartupFailure ? `${error.code ? ` code=${error.code}` : ''}${error.exitStatus !== undefined ? ` exit_status=${error.exitStatus}` : ''}` : '';
    const assertion = error instanceof StartupFailure && error.assertion ? ` assertion=${error.assertion}` : '';
    const count = error instanceof StartupFailure && error.countCategory ? ` count_category=${error.countCategory}` : '';
    const types = error instanceof StartupFailure && error.targetCounts ? ` page_count=${error.targetCounts.page} non_page_count=${error.targetCounts.nonPage} unknown_type_count=${error.targetCounts.unknown}` : '';
    report(`STOP: isolated mocked browser gate failed stage=${stage} category=${category}${resource}${startup}${assertion}${count}${types}; preserve any synthetic partial output; no automatic retry`);
    return false;
  }
}
async function localGet(url) {
  ensure(new URL(url).origin === ORIGIN || new URL(url).origin === debugOrigin, 'transport_target');
  const response = await fetch(url, { redirect: 'error', signal: AbortSignal.timeout(5000) });
  ensure(response.ok, 'frontend_readiness');
  const text = await response.text();
  ensure(text.length <= 2_000_000, 'response_bound');
  return text;
}
export async function readFrontendResource(url, resource, request = fetch) {
  let origin;
  try { origin = new URL(url).origin; } catch { throw new FrontendFailure('frontend_transport_target_failure', resource); }
  if (origin !== ORIGIN) throw new FrontendFailure('frontend_transport_target_failure', resource);
  let response;
  try { response = await request(url, { redirect: 'error', signal: AbortSignal.timeout(5000) }); }
  catch (error) {
    throw new FrontendFailure(['TimeoutError', 'AbortError'].includes(error?.name)
      ? 'frontend_request_timeout' : 'frontend_connection_failure', resource);
  }
  if (!response || typeof response.ok !== 'boolean') throw new FrontendFailure('frontend_unexpected_failure', resource);
  if (!response.ok) throw new FrontendFailure('frontend_http_status_failure', resource);
  let text;
  try { text = await response.text(); }
  catch (error) { throw new FrontendFailure(['TimeoutError', 'AbortError'].includes(error?.name)
    ? 'frontend_request_timeout' : 'frontend_response_read_failure', resource); }
  if (typeof text !== 'string') throw new FrontendFailure('frontend_unexpected_failure', resource);
  if (text.length > 2_000_000) throw new FrontendFailure('frontend_response_too_large', resource);
  return text;
}
export async function checkFrontend(get = readFrontendResource, read = readFile) {
  const load = async (url, resource) => {
    try { return await get(url, resource); }
    catch (error) { if (error instanceof FrontendFailure) throw error; throw new FrontendFailure('frontend_unexpected_failure', resource); }
  };
  const local = {}, served = { html: await load(ORIGIN + '/', 'frontend_origin') };
  for (const [key, file] of Object.entries({ main: 'main.jsx', app: 'App.jsx', api: 'services/api.js' })) {
    const resource = { main: 'main_jsx', app: 'app_jsx', api: 'api_js' }[key];
    try { local[key] = await read(path.join(root, 'frontend/src', file), 'utf8'); }
    catch { throw new FrontendFailure('frontend_local_source_unavailable', resource); }
    served[key] = await load(ORIGIN + '/src/' + file, resource);
  }
  return validateIdentityResponses(served, local);
}
export async function intercept(event, role, error, send) {
  const kind = classify(event.request.url, event.request.method, event.resourceType);
  if (kind === 'blocked') { await send('Fetch.failRequest', { requestId: event.requestId, errorReason: 'BlockedByClient' }); throw Error('unexpected_network'); }
  if (kind === 'mock') {
    let result;
    try { result = mockResponse(role, event.request, { error }); }
    catch { await send('Fetch.failRequest', { requestId: event.requestId, errorReason: 'BlockedByClient' }); throw Error('unexpected_api'); }
    await send('Fetch.fulfillRequest', { requestId: event.requestId, responseCode: result.status,
      responseHeaders: [{ name: 'Content-Type', value: 'application/json' }, { name: 'Access-Control-Allow-Origin', value: ORIGIN }, { name: 'Access-Control-Allow-Headers', value: 'authorization,content-type' }, { name: 'Access-Control-Allow-Methods', value: 'GET,POST,OPTIONS' }], body: Buffer.from(json(result.data)).toString('base64') });
    return;
  }
  if (new URL(event.request.url).pathname === '/@vite/client') {
    // No HMR sockets. Preserve Vite's normal CSS-module style injection.
    const stub = `export const createHotContext=()=>({data:{},accept(){},dispose(){},prune(){},on(){},invalidate(){}});
      export function updateStyle(id,css){let e=document.querySelector('style[data-visual-id="'+CSS.escape(id)+'"]');if(!e){e=document.createElement('style');e.dataset.visualId=id;document.head.append(e);}e.textContent=css;}
      export function removeStyle(id){document.querySelector('style[data-visual-id="'+CSS.escape(id)+'"]')?.remove();}
      export const injectQuery=(url,q)=>url+(url.includes('?')?'&':'?')+q;`;
    await send('Fetch.fulfillRequest', { requestId: event.requestId, responseCode: 200, responseHeaders: [{ name: 'Content-Type', value: 'text/javascript' }], body: Buffer.from(stub).toString('base64') });
  } else await send('Fetch.continueRequest', { requestId: event.requestId });
}
async function debugPortAbsent() {
  await new Promise((resolve, reject) => {
    const socket = createConnection({ host: '127.0.0.1', port: 9241 });
    socket.setTimeout(2000);
    socket.once('connect', () => { socket.destroy(); reject(Error('debug_port_busy')); });
    socket.once('timeout', () => { socket.destroy(); reject(Error('debug_port_unverified')); });
    socket.once('error', error => error.code === 'ECONNREFUSED' ? resolve() : reject(Error('debug_port_unverified')));
  });
}
async function outputDirectory() {
  // Only this new synthetic-output subtree is touched; never delete/reuse a run.
  let current = root;
  for (const component of OUTPUT.split('/')) {
    current = path.join(current, component);
    try { const info = await lstat(current); ensure(info.isDirectory() && !info.isSymbolicLink(), 'output_identity'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; await mkdir(current); }
  }
  const output = path.join(current, randomUUID());
  await mkdir(output); // Exclusive; failure preserves partial state.
  return output;
}
async function execute(setStage) {
  setStage('frontend_preflight');
  await checkFrontend(); // No browser/output writes if identity/config cannot be proven.
  setStage('debugging_port');
  await debugPortAbsent();
  setStage('chrome_availability');
  const chromePath = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
  ensure((await lstat(chromePath)).isFile(), 'chrome_missing');
  const catalogs = {};
  setStage('translation_catalog');
  for (const language of LANGUAGES) catalogs[language] = JSON.parse(await readFile(path.join(root, 'frontend/src/i18n/locales/application.' + language + '.json'), 'utf8'));
  setStage('output_creation');
  const output = await outputDirectory();
  setStage('chrome_startup');
  const { chrome, spawnFailure } = spawnChrome(chromePath, ['--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-component-update', '--disable-sync', '--disable-default-apps', '--disable-extensions', '--no-proxy-server', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1', '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=9241', '--user-data-dir=' + path.join(output, 'chrome-profile'), 'about:blank'], { windowsHide: true, stdio: 'ignore' });
  let ws, send, fatal = '', role = 'shop_owner', errorMode = false, inflight = 0, closing = false;

  const results = [];
  try {
    const socketUrl = await discoverDevtools(chrome, spawnFailure, async url => {
      const body = await localGet(url);
      await verifyListenerOwnership(chrome); // Do not trust discovery from another listener.
      return body;
    });
    await verifyListenerOwnership(chrome);
    await connectDevtools(socketUrl, socket => { ws = socket; });
    try { await verifyListenerOwnership(chrome); }
    catch (error) {
      // Never send Browser.close to a session whose listener cannot be verified.
      const unverifiedSocket = ws; ws = undefined;
      unverifiedSocket.close(); throw error;
    }
    let sequence = 0; const pending = new Map();
    send = (method, params = {}) => new Promise((resolve, reject) => {
      const id = ++sequence, timeout = setTimeout(() => { pending.delete(id); reject(Error('browser_timeout')); }, 10000);
      pending.set(id, { resolve: value => { clearTimeout(timeout); resolve(value); }, reject: () => { clearTimeout(timeout); reject(Error('browser_command')); } });
      ws.send(json({ id, method, params }));
    });
    ws.onclose = () => { if (!closing) fatal = 'browser_closed'; for (const value of pending.values()) value.reject(); pending.clear(); };
    ws.onmessage = event => {
      const data = JSON.parse(event.data);
      if (data.id) { const command = pending.get(data.id); pending.delete(data.id); if (command) data.error ? command.reject() : command.resolve(data.result); }
      else if (data.method === 'Fetch.requestPaused') {
        inflight++;
        intercept(data.params, role, errorMode, send).catch(() => { fatal = 'network_policy'; }).finally(() => { inflight--; });
      } else if (data.method === 'Runtime.exceptionThrown') fatal = 'page_exception';
      else if (data.method === 'Target.attachedToTarget') fatal = 'unexpected_target';
    };
    const evaluate = async expression => { const response = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }); ensure(!response.exceptionDetails, 'page_evaluation'); return response.result.value; };
    const wait = async expression => {
      for (let i = 0; i < 100; i++) {
        ensure(!fatal, fatal);
        try { if (!inflight && await evaluate(expression)) return; } catch (error) { if (error.message !== 'page_evaluation') throw error; }
        await pause(100);
      }
      throw Error('page_readiness');
    };
    setStage('network_setup');
    await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
    await send('Target.setAutoAttach', { autoAttach: true, waitForDebuggerOnStart: true, flatten: true });
    await send('Network.setBypassServiceWorker', { bypass: true }); await send('Network.setCacheDisabled', { cacheDisabled: true });
    await send('Fetch.enable', { patterns: [{ urlPattern: '*', requestStage: 'Request' }] });
    await send('Page.addScriptToEvaluateOnNewDocument', { source: `for(const key of ['WebSocket','EventSource','Worker','SharedWorker'])Object.defineProperty(window,key,{value:function(){window.__visualNetworkViolation=true;throw Error('Blocked test transport');}});window.open=()=>{window.__visualNetworkViolation=true;return null;};if(navigator.serviceWorker)navigator.serviceWorker.register=()=>{window.__visualNetworkViolation=true;return Promise.reject(Error('Blocked test worker'));};` });
    const setWidth = width => send('Emulation.setDeviceMetricsOverride', { width, height: 960, deviceScaleFactor: 1, mobile: width === 375 });
    const navigate = route => send('Page.navigate', { url: ORIGIN + route });
    const changeLanguage = async language => {
      await evaluate(`(()=>{const e=document.querySelector('.lankapex-language-selector select');if(!e)throw Error('selector');e.value=${json(language)};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
      await wait('document.documentElement.lang===' + json(language));
    };
    const clickText = async text => evaluate(`(()=>{const e=[...document.querySelectorAll('button')].find(e=>e.textContent.trim()===${json(text)}&&e.getBoundingClientRect().width);if(!e)throw Error('control');e.click();})()`);
    const shot = async (name, metadata) => {
      ensure(!fatal, fatal);
      if (metadata.state === 'normal') ensure(await evaluate('!document.querySelector("[role=alert]")'), 'unexpected_visible_error');
      await evaluate('document.fonts.ready.then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))');
      const metrics = await evaluate(`(()=>{const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return !e.closest('.sr-only')&&r.width>0&&r.height>0&&s.visibility!=='hidden';};const nodes=[...document.querySelectorAll('h1,h2,h3,h4,p,label,button,a,select')].filter(visible);return {overflow:document.documentElement.scrollWidth>innerWidth+2,clipped:nodes.filter(e=>e.scrollWidth>e.clientWidth+2&&!['auto','scroll'].includes(getComputedStyle(e).overflowX)).length,dialogOverflow:[...document.querySelectorAll('dialog[open]')].some(e=>{const r=e.getBoundingClientRect();return r.left<0||r.right>innerWidth+2||r.top<0||r.bottom>innerHeight+2;}),unicodeReplacement:document.body.innerText.includes('\\uFFFD'),transportViolation:!!window.__visualNetworkViolation};})()`);
      const screenshot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
      await writeFile(path.join(output, name + '.png'), Buffer.from(screenshot.data, 'base64'), { flag: 'wx' });
      results.push({ ...metadata, ...metrics });
      ensure(!metrics.overflow && !metrics.clipped && !metrics.dialogOverflow && !metrics.unicodeReplacement && !metrics.transportViolation, 'visual_layout');
    };
    setStage('browser_assertions');
    for (role of ROLES) {
      if (await evaluate('location.origin===' + json(ORIGIN))) await evaluate('sessionStorage.clear();localStorage.clear()');
      await setWidth(1366); await navigate('/login'); await wait('!!document.querySelector("#login-email")');
      await evaluate(`(()=>{const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;for(const [id,value]of [['login-email',${json(identity(role).email)}],['login-password','Synthetic-visual-input-only']]){const e=document.getElementById(id);set.call(e,value);e.dispatchEvent(new Event('input',{bubbles:true}));}})()`);
      for (const language of LANGUAGES) { await changeLanguage(language); ensure(await evaluate(`document.getElementById('login-email').value===${json(identity(role).email)}&&document.getElementById('login-password').value==='Synthetic-visual-input-only'`), 'form_state'); }
      await evaluate('document.querySelector("#login-email").closest("form").requestSubmit()');
      await wait('location.pathname===' + json(CASES[role][0].path));
      for (const language of LANGUAGES) {
        await wait('!!document.querySelector(".lankapex-language-selector select")'); await changeLanguage(language);
        const tr = key => catalogs[language][key] || key;
        for (const width of WIDTHS) {
          await setWidth(width);
          for (const item of CASES[role]) {
            await navigate(item.path);
            await wait('document.documentElement.lang===' + json(language) + '&&document.body.innerText.includes(' + json(tr(item.label)) + ')' + (item.marker ? '&&document.body.innerText.includes(' + json(item.marker) + ')' : '&&!!document.querySelector(\'[aria-labelledby="platform-overview-heading"][aria-busy="false"]\')'));
            if (role === 'shop_owner') ensure(await evaluate(`['credit-sales','repayments','products'].every(p=>document.querySelector('a[href="/shop-owner/'+p+'"]'))&&document.body.innerText.includes('LKR 100.25')`), 'owner_context');
            ensure(await evaluate(`[...document.querySelectorAll('a')].some(e=>e.getAttribute('href')===${json(item.path)})`), 'navigation_link');
            await shot(role + '-' + language + '-' + width + '-' + item.path.split('/').at(-1), { role, language, width, path: item.path, state: 'normal' });
            if (width === 375 && item === CASES[role][0]) {
              const open = tr('Open ' + MENU[role] + ' menu'), close = tr('Close ' + MENU[role] + ' menu');
              await evaluate(`document.querySelector('button[aria-label='+${json(JSON.stringify(open))}+']').click()`);
              await shot(role + '-' + language + '-375-menu', { role, language, width, state: 'menu' });
              await evaluate(`document.querySelector('button[aria-label='+${json(JSON.stringify(close))}+']').click()`);
            }
            if (role === 'admin' && width === 375 && item.path !== '/admin/dashboard') {
              await clickText(tr('View Details')); await wait('!!document.querySelector("#management-details-heading")');
              await clickText(tr('Approve') + ' ' + tr(item.path.endsWith('businesses') ? 'Business' : 'Driver'));
              await wait('!!document.querySelector("dialog[open] #admin-confirmation-title")');
              await shot('admin-' + language + '-375-' + item.path.split('/').at(-1) + '-confirmation', { role, language, width, state: 'confirmation' });
              await clickText(tr('Cancel')); // No approval submission is supported by the mock.
            }
          }
        }
        errorMode = true; await navigate(CASES[role][0].path); await wait('!!document.querySelector("[role=alert]")');
        await shot(role + '-' + language + '-375-error', { role, language, width: 375, state: 'error' }); errorMode = false;
        const denied = role === 'admin' ? '/customer/dashboard' : '/admin/dashboard';
        await navigate(denied); await wait('location.pathname===' + json(CASES[role][0].path));
      }
      await evaluate('sessionStorage.clear();localStorage.clear()');
      await send('Page.navigate', { url: 'about:blank' }); await wait('location.href==="about:blank"');
    }
    setStage('result_write');
    await writeFile(path.join(output, 'results.json'), json({ status: 'PASS', syntheticOnly: true, liveApiRequests: 0, results }), { flag: 'wx' });
    console.log('PASS: four-role mocked browser checks; synthetic screenshots and results saved under approved output root');
  } finally {
    closing = true;
    if (ws?.readyState === 1) { try { await send('Browser.close'); } catch { /* Only our child is terminated below. */ } ws.close(); }
    if (chrome.exitCode === null) chrome.kill();
    // Preserve synthetic partial artifacts for review; no automatic deletion/retry.
  }
}
export async function main(args = process.argv.slice(2), run = execute, report = message => console.error(message)) {
  const passed = await runWithDiagnostics(async setStage => {
    if (!executionGate(args)) { console.log('PASS: offline preparation only; no HTTP, browser or output writes'); return; }
    await run(setStage);
  }, report);
  if (!passed) process.exitCode = 1;
  return passed;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
