import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import process from 'node:process';
import { readFile } from 'node:fs/promises';
import { ORIGIN, API, OUTPUT, TOKEN, CASES, ROLES, executionGate, identity, classify, validateIdentityResponses, mockResponse } from '../scripts/fourRoleMockPolicy.mjs';
import { checkFrontend, readFrontendResource, intercept, runWithDiagnostics, main, spawnChrome, discoverDevtools, connectDevtools, initialTabCountCategory, targetTypeCounts, verifyListenerOwnership } from '../scripts/verifyFourRoleMockBrowser.mjs';
import { parseCustomerResponse } from '../src/utils/customerDashboard.js';
import { parseCustomerPage } from '../src/utils/customerAccounts.js';
import { parseCustomerOrdersPage } from '../src/utils/customerOrders.js';
import { parseDriverResponse } from '../src/utils/driverDashboard.js';
import { parseAvailableJobs } from '../src/utils/driverJobs.js';
import { parseDeliveryPage } from '../src/utils/driverDeliveries.js';
import { parseManagementList, parseManagementDetail } from '../src/utils/adminManagement.js';
import { parseAdminOverview, parseAdminActivity } from '../src/utils/adminDashboard.js';

const request = (route, method = 'GET', patch = {}) => ({ url: API + route, method, headers: { Authorization: 'Bearer ' + TOKEN }, ...patch });
const get = (role, route) => mockResponse(role, request(route)).data;
const sourceMap = original => '\n//# sourceMappingURL=data:application/json;base64,' + Buffer.from(JSON.stringify({ sourcesContent: [original] })).toString('base64');
function readiness() {
  const local = { main: 'workspace-main', app: 'workspace-app', api: 'workspace-api' };
  return { local, served: { html: '<script src="/@vite/client"></script><script src="/src/main.jsx"></script>', main: sourceMap(local.main), app: sourceMap(local.app), api: 'import.meta.env = ' + JSON.stringify({ VITE_API_URL: API }) + ';' + sourceMap(local.api) } };
}
test('execution is opt-in and pinned to the running 5173 frontend and exact output root', () => {
  assert.equal(executionGate([]), false);
  assert.equal(executionGate(['--execute', '--confirm-origin', ORIGIN, '--confirm-output', OUTPUT]), true);
  for (const args of [['--execute'], ['--execute', '--confirm-origin', 'http://127.0.0.1:5175', '--confirm-output', OUTPUT], ['--execute', '--confirm-origin', ORIGIN, '--confirm-output', '../other']]) assert.throws(() => executionGate(args));
});
test('readiness requires matching workspace source maps and the exact effective API configuration', () => {
  const { local, served } = readiness();
  assert.equal(validateIdentityResponses(served, local), true);
  for (const key of ['main', 'app', 'api', 'html']) assert.throws(() => validateIdentityResponses({ ...served, [key]: 'wrong frontend' }, local));
  for (const env of [{ VITE_API_URL: 'http://127.0.0.1:8014/api/v1' }, { VITE_API_URL: API, VITE_SECRET: 'synthetic-sentinel' }]) assert.throws(() => validateIdentityResponses({ ...served, api: 'import.meta.env = ' + JSON.stringify(env) + ';' + sourceMap(local.api) }, local));
});
test('readiness only requests existing frontend resources, using injected offline responses', async () => {
  const { local, served } = readiness(), calls = [];
  const map = { '/': served.html, '/src/main.jsx': served.main, '/src/App.jsx': served.app, '/src/services/api.js': served.api };
  assert.equal(await checkFrontend(async url => { calls.push(url); return map[new URL(url).pathname]; }, async file => local[file.endsWith('main.jsx') ? 'main' : file.endsWith('App.jsx') ? 'app' : 'api']), true);
  assert.equal(calls.length, 4);
  assert.ok(calls.every(url => new URL(url).origin === ORIGIN && !url.includes('/api/v1')));
});
test('unexpected network targets, websocket transports, traversal and local backend documents fail closed', () => {
  for (const url of ['https://example.com/', 'http://127.0.0.1:5175/src/App.jsx', 'http://127.0.0.1:8001/docs', 'http://127.0.0.1:3306/', 'ws://127.0.0.1:5173/', ORIGIN + '/@fs/C:/private', ORIGIN + '/api/v1/auth/me', ORIGIN + '/backend/.env']) assert.equal(classify(url), 'blocked', url);
  assert.equal(classify(ORIGIN + '/src/i18n/locales/application.ta.json?import'), 'frontend');
  assert.equal(classify(ORIGIN + '/node_modules/@fontsource/inter/400.css'), 'frontend');
  assert.equal(classify(API + '/auth/me'), 'mock');
});
test('all intercepted API requests are fulfilled locally, never continued', async () => {
  const calls = [], send = async (name, args) => calls.push([name, args]);
  await intercept({ requestId: 'synthetic', request: request('/auth/me') }, 'customer', false, send);
  assert.deepEqual(calls.map(c => c[0]), ['Fetch.fulfillRequest']);
  calls.length = 0;
  for (const route of ['/unknown', '/admin/overview']) await assert.rejects(intercept({ requestId: 'synthetic', request: request(route) }, 'customer', false, send));
  assert.ok(calls.every(c => c[0] === 'Fetch.failRequest'));
  await assert.rejects(intercept({ requestId: 'synthetic', request: { url: 'https://example.com/', method: 'GET' } }, 'customer', false, send));
});
test('normal login and auth/me are mocked; real identities, tokens and mutations are rejected', () => {
  for (const role of ROLES) {
    const login = request('/auth/login', 'POST', { postData: new URLSearchParams({ username: identity(role).email, password: 'Synthetic-visual-input-only' }).toString() });
    assert.equal(mockResponse(role, login).data.access_token, TOKEN);
    assert.deepEqual(get(role, '/auth/me'), identity(role));
    assert.throws(() => mockResponse(role, { ...login, postData: 'username=real&password=real' }));
    assert.throws(() => mockResponse(role, request('/auth/me', 'GET', { headers: { Authorization: 'Bearer not-fixture' } })));
    for (const method of ['POST', 'PATCH', 'DELETE']) assert.throws(() => mockResponse(role, request('/admin/businesses/7/decision', method)));
  }
});
test('Customer dashboard, recent orders and My Shops use existing parsers and exact financial strings', () => {
  for (const [section, url] of [['summary', '/dashboard/summary'], ['shops', '/shops'], ['accounts', '/credit-accounts'], ['transactions', '/transactions']]) assert.ok(parseCustomerResponse(section, get('customer', '/customer' + url)));
  const shops = parseCustomerPage('shops', get('customer', '/customer/shops?page=1&page_size=10'), 1);
  assert.equal(shops.items[0].outstanding_balance, '100.25');
  assert.ok(parseCustomerOrdersPage(get('customer', '/customer/orders?page=1&page_size=5'), 1, 5));
});
test('Driver fixtures match current dashboard, Available Jobs and Assigned Deliveries contracts', () => {
  for (const [section, url] of [['profile', '/profile'], ['summary', '/dashboard/summary'], ['deliveries', '/deliveries']]) assert.ok(parseDriverResponse(section, get('driver', '/driver' + url), 7));
  assert.equal(parseAvailableJobs(get('driver', '/driver/jobs?page=1&page_size=10'), 7, 1).items.length, 1);
  assert.equal(parseDeliveryPage(get('driver', '/driver/deliveries?page=1&page_size=10'), 7, 1, false).deliveries.length, 2);
});
test('Admin pending approvals retain real list/detail contracts with synthetic ownership', () => {
  assert.ok(parseAdminOverview(get('admin', '/admin/overview')));
  assert.ok(parseAdminActivity(get('admin', '/admin/audit-events?limit=5&offset=0')));
  for (const [kind, route] of [['business', 'businesses'], ['driver', 'drivers']]) {
    const filters = { q: '', status: '', approval_status: '', offset: 0 };
    assert.equal(parseManagementList(kind, get('admin', '/admin/' + route + '?limit=10&offset=0'), filters).rows.length, 1);
    assert.ok(parseManagementDetail(kind, get('admin', '/admin/' + route + '/7'), 7));
  }
});
test('Owner credit overview and transactions are deterministic and business-scoped', () => {
  assert.equal(get('shop_owner', '/shop-owner/dashboard/summary?business_id=2').total_outstanding, '100.25');
  assert.equal(get('shop_owner', '/shop-owner/dashboard/recent-transactions?business_id=2').transactions[1].amount, '30.10');
  assert.throws(() => get('shop_owner', '/shop-owner/dashboard/summary?business_id=3'));
});
test('unknown endpoints, preflights, query parameters and cross-role API access are blocked', () => {
  for (const [role, route] of [['customer', '/admin/overview'], ['admin', '/customer/dashboard/summary'], ['driver', '/driver/jobs?private=true'], ['shop_owner', '/shop-owner/dashboard/summary?business_id=2&sql=anything']]) assert.throws(() => get(role, route));
  assert.throws(() => mockResponse('driver', request('/unknown', 'OPTIONS')));
  assert.equal(mockResponse('driver', request('/driver/jobs', 'OPTIONS')).status, 200);
});
test('visible failure fixtures do not leak request data; source contains no server startup or live account access', async () => {
  const response = mockResponse('admin', request('/admin/overview'), { error: true });
  assert.deepEqual(response, { status: 503, data: { detail: 'Synthetic service unavailable' } });
  const source = await readFile(new URL('../scripts/verifyFourRoleMockBrowser.mjs', import.meta.url), 'utf8');
  assert.ok(!/createServer|listen\(|mysql|pymysql|dpapi|start_demo|start_tamil/i.test(source));
  assert.ok(source.includes('Network.setBypassServiceWorker') && source.includes("urlPattern: '*'"));
  assert.ok(source.includes("flag: 'wx'") && !source.includes('remote-allow-origins=*'));
  assert.ok(!source.includes('console.error(error') && !source.includes('innerText)'));
});
test('every planned route has English, Tamil and Sinhala labels', async () => {
  for (const language of ['en', 'ta', 'si']) {
    const catalog = JSON.parse(await readFile(new URL('../src/i18n/locales/application.' + language + '.json', import.meta.url), 'utf8'));
    for (const item of Object.values(CASES).flat()) assert.ok(catalog[item.label], item.label);
  }
});

test('diagnostics identify major phases using synthetic failures without I/O', async () => {
  const cases = [
    ['confirmation', 'confirmation', 'confirmation_mismatch'],
    ['frontend_preflight', 'frontend_identity', 'frontend_identity_mismatch'],
    ['frontend_preflight', 'source_map', 'source_map_mismatch'],
    ['frontend_preflight', 'frontend_configuration', 'api_configuration_mismatch'],
    ['debugging_port', 'debug_port_busy', 'debugging_port_occupied'],
    ['debugging_port', 'unknown', 'debugging_port_unverified'],
    ['chrome_availability', 'ENOENT private path', 'chrome_unavailable'],
    ['translation_catalog', 'invalid JSON secret', 'translation_catalog_failure'],
    ['output_creation', 'EACCES private path', 'output_creation_failure'],
    ['chrome_startup', 'browser_start', 'chrome_startup_failure'],
    ['network_setup', 'network_policy', 'network_isolation_failure'],
    ['browser_assertions', 'visual_layout', 'browser_assertion_failure'],
    ['browser_assertions', 'network_policy', 'network_isolation_failure'],
    ['result_write', 'disk full', 'output_write_failure'],
  ];
  for (const [stage, message, category] of cases) {
    const logs = [];
    const passed = await runWithDiagnostics(async setStage => { setStage(stage); throw Error(message); }, value => logs.push(value));
    assert.equal(passed, false);
    assert.equal(logs.length, 1);
    assert.ok(logs[0].includes(`stage=${stage} category=${category};`));
  }
});

test('unexpected exceptions and untrusted stages never disclose error data', async () => {
  for (const error of [Error('https://private.invalid/?token=synthetic-secret'), 'cookie=synthetic-secret', null]) {
    const logs = [];
    assert.equal(await runWithDiagnostics(async setStage => { setStage('frontend_preflight'); throw error; }, value => logs.push(value)), false);
    assert.ok(logs[0].includes('category=frontend_unexpected_failure'));
    assert.ok(!/secret|cookie|private|https/.test(logs[0]));
  }
  const logs = [];
  assert.equal(await runWithDiagnostics(async setStage => setStage('private-stage-secret'), value => logs.push(value)), false);
  assert.ok(!logs[0].includes('private-stage-secret'));
});

test('failure before output creation is reported without creating output or retrying', async () => {
  const logs = []; let executions = 0, outputCreated = false;
  const previous = process.exitCode;
  try {
    assert.equal(await main(['--execute', '--confirm-origin', ORIGIN, '--confirm-output', OUTPUT], async setStage => {
      executions++; setStage('frontend_preflight');
      await checkFrontend(async () => { throw Error('synthetic-secret'); }, async () => { throw Error('must not read'); });
      outputCreated = true;
    }, value => logs.push(value)), false);
    assert.equal(process.exitCode, 1);
    assert.equal(executions, 1); assert.equal(outputCreated, false);
    assert.equal(logs.length, 1); assert.ok(!logs[0].includes('synthetic-secret'));
  } finally { process.exitCode = previous; }
});

test('diagnostic boundary preserves synthetic partial artifacts and never retries', async () => {
  const partial = new Map(); let executions = 0;
  assert.equal(await runWithDiagnostics(async setStage => {
    executions++; setStage('browser_assertions'); partial.set('synthetic.png', 'synthetic bytes');
    throw Error('visual_layout');
  }, () => {}), false);
  assert.equal(executions, 1); assert.equal(partial.get('synthetic.png'), 'synthetic bytes');
  const logs = [];
  assert.equal(await runWithDiagnostics(async () => {}, value => logs.push(value)), true);
  assert.deepEqual(logs, []);
});

test('source-map failure remains distinct from identity and API configuration failures', () => {
  const { served, local } = readiness();
  assert.throws(() => validateIdentityResponses({ ...served, html: '' }, local), /^Error: frontend_identity$/);
  assert.throws(() => validateIdentityResponses({ ...served, main: '' }, local), /^Error: source_map$/);
  assert.throws(() => validateIdentityResponses({ ...served, api: sourceMap(local.api) }, local), /^Error: frontend_configuration$/);
});

test('frontend request diagnostics classify synthetic failures without exposing details or retrying', async () => {
  const secret = 'synthetic-private-token';
  const timedOut = Object.assign(Error(secret), { name: 'TimeoutError' });
  const cases = [
    ['frontend_connection_failure', async () => { throw Error(secret); }],
    ['frontend_request_timeout', async () => { throw timedOut; }],
    ['frontend_http_status_failure', async () => ({ ok: false })],
    ['frontend_response_read_failure', async () => ({ ok: true, text: async () => { throw Error(secret); } })],
    ['frontend_request_timeout', async () => ({ ok: true, text: async () => { throw timedOut; } })],
    ['frontend_response_too_large', async () => ({ ok: true, text: async () => 'x'.repeat(2_000_001) })],
    ['frontend_unexpected_failure', async () => null],
    ['frontend_unexpected_failure', async () => ({ ok: true, text: async () => null })],
  ];
  for (const [category, response] of cases) {
    const logs = []; let requests = 0;
    assert.equal(await runWithDiagnostics(async setStage => {
      setStage('frontend_preflight');
      await readFrontendResource(ORIGIN + '/src/App.jsx', 'app_jsx', async (_url, options) => {
        requests++; assert.equal(options.redirect, 'error'); assert.ok(options.signal); return response();
      });
    }, message => logs.push(message)), false);
    assert.equal(requests, 1);
    assert.ok(logs[0].includes(`category=${category} resource=app_jsx;`));
    assert.ok(!logs[0].includes(secret)); assert.ok(!logs[0].includes(ORIGIN));
  }
});

test('frontend transport rejects invalid and unexpected origins before calling transport', async () => {
  for (const url of ['not a url', 'https://example.invalid/?token=synthetic-private-token']) {
    let requests = 0; const logs = [];
    assert.equal(await runWithDiagnostics(async setStage => {
      setStage('frontend_preflight');
      await readFrontendResource(url, 'untrusted-label-secret', async () => { requests++; });
    }, message => logs.push(message)), false);
    assert.equal(requests, 0);
    assert.ok(logs[0].includes('category=frontend_transport_target_failure resource=frontend_origin;'));
    assert.ok(!logs[0].includes('secret')); assert.ok(!logs[0].includes(url));
  }
});

test('local source failures report only fixed main/app/api resource labels', async () => {
  for (const [missing, resource] of [['main', 'main_jsx'], ['app', 'app_jsx'], ['api', 'api_js']]) {
    const { local, served } = readiness(); const logs = [];
    const map = { '/': served.html, '/src/main.jsx': served.main, '/src/App.jsx': served.app, '/src/services/api.js': served.api };
    assert.equal(await runWithDiagnostics(async setStage => {
      setStage('frontend_preflight');
      await checkFrontend(async url => map[new URL(url).pathname], async file => {
        const key = file.endsWith('main.jsx') ? 'main' : file.endsWith('App.jsx') ? 'app' : 'api';
        if (key === missing) throw Error('synthetic-private-path');
        return local[key];
      });
    }, message => logs.push(message)), false);
    assert.ok(logs[0].includes(`category=frontend_local_source_unavailable resource=${resource};`));
    assert.ok(!logs[0].includes('synthetic-private-path'));
  }
});

test('frontend response boundary is unchanged and injected unexpected failures retain a fixed label', async () => {
  assert.equal((await readFrontendResource(ORIGIN, 'frontend_origin', async () => ({ ok: true, text: async () => 'x'.repeat(2_000_000) }))).length, 2_000_000);
  const logs = [];
  assert.equal(await runWithDiagnostics(async setStage => {
    setStage('frontend_preflight');
    await checkFrontend(async () => { throw Error('synthetic-secret'); });
  }, message => logs.push(message)), false);
  assert.ok(logs[0].includes('category=frontend_unexpected_failure resource=frontend_origin;'));
  assert.ok(!logs[0].includes('synthetic-secret'));
});

const startupDiagnostic = async run => {
  const logs = [];
  assert.equal(await runWithDiagnostics(async setStage => { setStage('chrome_startup'); await run(); }, message => logs.push(message)), false);
  assert.equal(logs.length, 1);
  assert.ok(!/synthetic-secret|private-path|cookie|Authorization/.test(logs[0]));
  return logs[0];
};
const fakeChrome = () => ({ exitCode: null, signalCode: null, on() {} });
const discovery = JSON.stringify([{ url: 'about:blank', webSocketDebuggerUrl: 'ws://127.0.0.1:9241/devtools/page/synthetic' }]);

test('Chrome synchronous and asynchronous spawn failures expose only allowlisted codes and never relaunch', async () => {
  let calls = 0;
  const message = await startupDiagnostic(() => spawnChrome('synthetic', [], {}, () => { calls++; throw Object.assign(Error('synthetic-secret'), { code: 'EACCES' }); }));
  assert.ok(message.includes('category=chrome_spawn_failure code=EACCES;')); assert.equal(calls, 1);
  let handler;
  const { chrome, spawnFailure } = spawnChrome('synthetic', [], {}, () => ({ ...fakeChrome(), on(_event, callback) { handler = callback; } }));
  handler(Object.assign(Error('private-path'), { code: 'synthetic-secret' }));
  const asyncMessage = await startupDiagnostic(() => discoverDevtools(chrome, spawnFailure, async () => { throw Error('must not request'); }));
  assert.ok(asyncMessage.includes('category=chrome_spawn_failure;')); assert.ok(!asyncMessage.includes(' code='));
});

test('premature Chrome exit reports numeric status only, including after a discovery read', async () => {
  for (const status of [0, 17, 'synthetic-secret']) {
    const chrome = { ...fakeChrome(), exitCode: status };
    const message = await startupDiagnostic(() => discoverDevtools(chrome, () => undefined));
    assert.ok(message.includes('category=chrome_premature_exit'));
    assert.equal(message.includes('exit_status='), typeof status === 'number');
  }
  const chrome = fakeChrome();
  assert.ok((await startupDiagnostic(() => discoverDevtools(chrome, () => undefined, async () => { chrome.exitCode = 23; return discovery; }))).includes('exit_status=23'));
});

test('DevTools discovery timeout preserves the existing bounded readiness polling', async () => {
  let reads = 0, waits = 0;
  const message = await startupDiagnostic(() => discoverDevtools(fakeChrome(), () => undefined, async () => { reads++; throw Error('synthetic-secret'); }, async ms => { assert.equal(ms, 150); waits++; }));
  assert.ok(message.includes('category=devtools_discovery_timeout;'));
  assert.equal(reads, 40); assert.equal(waits, 40);
});

test('DevTools malformed discovery and identity mismatches stop immediately', async () => {
  const cases = [
    ['invalid json synthetic-secret', 'devtools_discovery_malformed'],
    ['null', 'devtools_discovery_malformed'],
    ['[null]', 'devtools_discovery_malformed'],
    ['[]', 'devtools_identity_mismatch'],
    [JSON.stringify([{ url: 'about:blank', webSocketDebuggerUrl: 'invalid synthetic-secret' }]), 'devtools_discovery_malformed'],
    [discovery.replace('about:blank', 'https://synthetic-secret.invalid'), 'devtools_identity_mismatch'],
    [discovery.replace('9241', '9242'), 'devtools_identity_mismatch'],
    [discovery.replace('127.0.0.1', 'example.invalid'), 'devtools_identity_mismatch'],
    [discovery.replace('ws:', 'wss:'), 'devtools_identity_mismatch'],
    [JSON.stringify([...JSON.parse(discovery), ...JSON.parse(discovery)]), 'devtools_identity_mismatch'],
  ];
  for (const [body, category] of cases) {
    let reads = 0;
    const message = await startupDiagnostic(() => discoverDevtools(fakeChrome(), () => undefined, async () => { reads++; return body; }, async () => { throw Error('must not poll again'); }));
    assert.ok(message.includes(`category=${category}`)); assert.equal(reads, 1);
    if (category === 'devtools_discovery_malformed') assert.ok(!message.includes(' assertion='));
  }
  const url = await discoverDevtools(fakeChrome(), () => undefined, async () => discovery);
  assert.equal(url.origin, 'ws://127.0.0.1:9241');
});

test('DevTools identity STOP reports exactly one fixed assertion in the original validation order', async () => {
  const tab = JSON.parse(discovery)[0];
  const cases = [
    [[], 'initial_tab_count'],
    [[tab, { ...tab, url: 'https://synthetic-secret.invalid' }], 'initial_tab_count'],
    [[{ ...tab, url: 'https://synthetic-secret.invalid', webSocketDebuggerUrl: 'invalid' }], 'initial_tab_url'],
    [[{ ...tab, webSocketDebuggerUrl: 'wss://synthetic-secret.invalid:9999/private' }], 'websocket_host'],
    [[{ ...tab, webSocketDebuggerUrl: 'wss://127.0.0.1:9999/private' }], 'websocket_port'],
    [[{ ...tab, webSocketDebuggerUrl: 'wss://127.0.0.1:9241/private' }], 'websocket_protocol'],
  ];
  for (const [tabs, assertion] of cases) {
    let reads = 0;
    const message = await startupDiagnostic(() => discoverDevtools(fakeChrome(), () => undefined, async () => { reads++; return JSON.stringify(tabs); }));
    assert.equal(reads, 1);
    assert.ok(message.includes(`category=devtools_identity_mismatch assertion=${assertion}`));
    assert.equal(message.includes(' count_category='), assertion === 'initial_tab_count');
    assert.equal((message.match(/ assertion=/g) || []).length, 1);
    assert.ok(!/wss?:|https:|private|9999|9241/.test(message));
  }
  // Structural validation still precedes count and tab-URL validation.
  const malformed = await startupDiagnostic(() => discoverDevtools(fakeChrome(), () => undefined, async () => JSON.stringify([tab, null])));
  assert.ok(malformed.includes('category=devtools_discovery_malformed;'));
  assert.ok(!malformed.includes(' assertion='));
  assert.equal((await discoverDevtools(fakeChrome(), () => undefined, async () => discovery)).href, tab.webSocketDebuggerUrl);
});

test('initial count failures report only bounded categories and preserve strict one-tab acceptance', async () => {
  const tab = JSON.parse(discovery)[0];
  for (const [size, category] of [[0, 'zero'], [2, 'two'], [3, 'three_or_more'], [12, 'three_or_more']]) {
    let reads = 0;
    const message = await startupDiagnostic(() => discoverDevtools(fakeChrome(), () => undefined, async () => {
      reads++; return JSON.stringify(Array.from({ length: size }, () => ({ ...tab, title: 'synthetic-secret', id: 'synthetic-secret' })));
    }));
    assert.equal(reads, 1);
    assert.ok(message.includes(`assertion=initial_tab_count count_category=${category} `));
    assert.ok(!/about:blank|devtools\/page|ws:|9241|title|synthetic-secret/.test(message));
  }
  const messages = [];
  assert.equal(await runWithDiagnostics(async () => {
    assert.equal((await discoverDevtools(fakeChrome(), () => undefined, async () => discovery)).href, tab.webSocketDebuggerUrl);
  }, message => messages.push(message)), true);
  assert.deepEqual(messages, []);
  // Unknown is a defensive sanitizer fallback, not an alternative accepted count.
  for (const invalid of [undefined, null, '2', 'synthetic-secret', NaN, Infinity, -1, 1.5, 1]) {
    assert.equal(initialTabCountCategory(invalid), 'unknown');
  }
});

test('target classification uses type only with bounded counts and no filtering', async () => {
  assert.deepEqual(targetTypeCounts(null), { page: 'unknown', nonPage: 'unknown', unknown: 'unknown' });
  assert.deepEqual(targetTypeCounts([]), { page: 'zero', nonPage: 'zero', unknown: 'zero' });
  assert.deepEqual(targetTypeCounts([{ type: 'page', url: 'synthetic-secret' }, { type: 'worker' }, {}]), { page: 'one', nonPage: 'one', unknown: 'one' });
  assert.deepEqual(targetTypeCounts([{ type: 'page' }, { type: 'page' }, { type: '' }, { type: null }, { type: 7 }, { type: ' ' }]), { page: 'two', nonPage: 'zero', unknown: 'three_or_more' });
  assert.equal(targetTypeCounts(Array.from({ length: 4 }, () => ({ type: 'worker' }))).nonPage, 'three_or_more');
  const tab = JSON.parse(discovery)[0];
  const message = await startupDiagnostic(() => discoverDevtools(fakeChrome(), () => undefined, async () => JSON.stringify([
    { ...tab, type: 'page' }, { ...tab, type: 'service_worker' }, { ...tab, title: 'synthetic-secret', id: 'synthetic-secret' },
  ])));
  assert.ok(message.includes('count_category=three_or_more page_count=one non_page_count=one unknown_type_count=one;'));
});

test('Windows listener ownership accepts only direct tracked child with sanitized metadata', async () => {
  const chrome = { ...fakeChrome(), pid: 12345 }; let calls = 0;
  await verifyListenerOwnership(chrome, async (file, args, options) => {
    calls++;
    assert.equal(file, 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe');
    assert.deepEqual(args.slice(0, 3), ['-NoProfile', '-NonInteractive', '-Command']);
    assert.ok(args[3].includes('Get-NetTCPConnection -State Listen -LocalPort 9241'));
    assert.ok(args[3].includes("LocalAddress -ne '127.0.0.1'"));
    assert.ok(args[3].includes('$rows.Count -ne 1'));
    assert.ok(args[3].includes('OwningProcess -ne 12345'));
    assert.ok(!/Stop-Process|taskkill|Remove-|Set-/.test(args[3]));
    assert.equal(options.windowsHide, true); assert.equal(options.timeout, 5000);
    return 'matched\r\n';
  }, 'win32');
  assert.equal(calls, 1);
  for (const [output, category] of [['mismatch', 'devtools_owner_mismatch'], ['ambiguous', 'devtools_owner_ambiguous'], ['unavailable', 'devtools_owner_unavailable'], ['synthetic-secret', 'devtools_owner_unavailable']]) {
    const message = await startupDiagnostic(() => verifyListenerOwnership(chrome, async () => output, 'win32'));
    assert.ok(message.includes(`category=${category};`)); assert.ok(!message.includes('12345'));
  }
});

test('listener metadata failure, unsupported platform and child exit fail closed without retry', async () => {
  const chrome = { ...fakeChrome(), pid: 12345 }; let calls = 0;
  assert.ok((await startupDiagnostic(() => verifyListenerOwnership(chrome, async () => { calls++; throw Error('synthetic-secret'); }, 'win32'))).includes('category=devtools_owner_unavailable;'));
  assert.equal(calls, 1);
  for (const child of [{ ...chrome, pid: undefined }, { ...chrome, exitCode: 0 }, { ...chrome, signalCode: 'SIGTERM' }]) {
    await startupDiagnostic(() => verifyListenerOwnership(child, async () => { throw Error('must not run'); }, 'win32'));
  }
  await startupDiagnostic(() => verifyListenerOwnership(chrome, async () => { throw Error('must not run'); }, 'linux'));
  const exiting = { ...chrome };
  assert.ok((await startupDiagnostic(() => verifyListenerOwnership(exiting, async () => { exiting.exitCode = 1; return 'matched'; }, 'win32'))).includes('category=devtools_owner_unavailable;'));
});

test('ownership failures during discovery propagate immediately without readiness retry', async () => {
  let reads = 0, waits = 0;
  const message = await startupDiagnostic(() => discoverDevtools(fakeChrome(), () => undefined, async () => {
    reads++;
    await verifyListenerOwnership({ ...fakeChrome(), pid: 12345 }, async () => 'mismatch', 'win32');
    return discovery;
  }, async () => { waits++; }));
  assert.ok(message.includes('category=devtools_owner_mismatch;'));
  assert.equal(reads, 1); assert.equal(waits, 0);
});

test('DevTools WebSocket construction, connection, close and timeout failures are sanitized', async () => {
  assert.ok((await startupDiagnostic(() => connectDevtools('synthetic', () => {}, () => { throw Error('synthetic-secret'); }))).includes('category=devtools_websocket_failure;'));
  for (const event of ['onerror', 'onclose', 'timeout', 'onopen']) {
    const socket = {}; let expire, retained, cancelled = 0;
    const run = () => {
      const promise = connectDevtools('synthetic', value => { retained = value; }, () => socket, (callback, ms) => { assert.equal(ms, 5000); expire = callback; return 1; }, () => { cancelled++; });
      if (event === 'timeout') expire(); else socket[event]();
      return promise;
    };
    if (event === 'onopen') await run();
    else assert.ok((await startupDiagnostic(run)).includes(`category=${event === 'timeout' ? 'devtools_websocket_timeout' : 'devtools_websocket_failure'};`));
    assert.equal(retained, socket); assert.equal(cancelled, event === 'timeout' ? 0 : 1);
  }
});
