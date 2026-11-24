import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createAuthSession, getLoginErrorMessage, validateIdentity } from "../src/utils/authSession.js";
import { getDashboardPath, getLoginPath } from "../src/utils/roleRoutes.js";

const key = "lankapex_access_token";
const identity = (role = "customer", id = 1) => ({ user_id: id, platform_role: role, account_status: "active", full_name: "Test User" });
function setup(overrides = {}) {
  const data = new Map();
  const calls = [];
  const session = createAuthSession({
    storage: () => ({ getItem: k => data.get(k), setItem: (k, v) => data.set(k, v), removeItem: k => data.delete(k) }),
    loginUser: async (...args) => { calls.push(args); return { access_token: "token" }; },
    getCurrentUser: async () => identity(), ...overrides,
  });
  return { session, data, calls };
}
function deferred() { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b; }); return { promise, resolve, reject }; }

for (const [role, route] of Object.entries({ shop_owner: "/shop-owner/dashboard", customer: "/customer/dashboard", driver: "/driver/dashboard", admin: "/admin/dashboard" })) {
  test(role + " uses backend identity and its existing dashboard", async () => {
    const { session, data } = setup({ getCurrentUser: async () => identity(role) });
    const user = await session.login("test@example.com", "test password");
    assert.equal(getDashboardPath(user.platform_role), route);
    assert.equal(session.getSnapshot().user.platform_role, role);
    assert.equal(data.get(key), "token");
  });
}
for (const patch of [{ platform_role: null }, { platform_role: "other" }, { platform_role: "toString" }, { platform_role: "__proto__" }, { account_status: "pending" }, { account_status: "suspended" }, { user_id: null }]) {
  test("rejects unverified identity " + JSON.stringify(patch), async () => {
    const { session, data } = setup({ getCurrentUser: async () => ({ ...identity(), ...patch }) });
    await assert.rejects(session.login("test@example.com", "password"));
    assert.equal(data.size, 0); assert.equal(session.getSnapshot().user, null);
  });
}
test("unsupported route keys cannot inherit Object prototype values", () => { for (const role of [null, undefined, "other", "toString", "constructor", "__proto__"]) assert.equal(getDashboardPath(role), "/login"); });
test("restoration verifies stored token and ignores local role values", async () => {
  const { session, data } = setup({ getCurrentUser: async token => { assert.equal(token, "stored"); return identity("driver"); } });
  data.set(key, "stored"); data.set("role", "admin");
  await session.restore(); assert.equal(session.getSnapshot().user.platform_role, "driver"); assert.equal(session.getSnapshot().loading, false);
});
test("expired JWT and failed restoration clear the session", async () => {
  for (const error of [{ response: { status: 401 } }, { response: { status: 403 } }, new Error("Network")]) {
    const { session, data } = setup({ getCurrentUser: async () => { throw error; } }); data.set(key, "expired");
    await session.restore(); assert.equal(data.has(key), false); assert.equal(session.getSnapshot().user, null); assert.equal(session.getSnapshot().token, null); assert.equal(session.getSnapshot().loading, false);
  }
});
test("no stored token finishes restoration without API calls", async () => {
  const { session } = setup({ getCurrentUser: () => { throw new Error("Unexpected call"); } });
  await session.restore(); assert.equal(session.getSnapshot().loading, false);
});
test("logout during restoration prevents a late session resurrection", async () => {
  const response = deferred(); const { session, data } = setup({ getCurrentUser: () => response.promise }); data.set(key, "old");
  const pending = session.restore(); session.logout(); response.resolve(identity()); await pending;
  assert.equal(data.has(key), false); assert.equal(session.getSnapshot().user, null);
});
test("logout during login prevents late persistence", async () => {
  const response = deferred(); const { session, data } = setup({ loginUser: () => response.promise });
  const pending = session.login("test@example.com", "password"); session.logout(); response.resolve({ access_token: "late" });
  await assert.rejects(pending, /cancelled/); assert.equal(data.size, 0); assert.equal(session.getSnapshot().user, null);
});
test("duplicate login submissions share one in-flight request", async () => {
  const response = deferred(); let count = 0;
  const { session } = setup({ loginUser: () => { count++; return response.promise; } });
  const first = session.login("a@example.com", "password"), second = session.login("a@example.com", "password");
  assert.equal(first, second); assert.equal(count, 1); response.resolve({ access_token: "token" }); await first;
});
test("signed-in accounts cannot be replaced without explicit logout", async () => {
  const { session, data, calls } = setup();
  await session.login("a@example.com", "password");
  await assert.rejects(session.login("b@example.com", "password"), {code:'BROWSER_ALREADY_SIGNED_IN'});
  assert.equal(session.getSnapshot().user.user_id,1);assert.equal(data.get(key),'token');assert.equal(calls.length,1);
  session.logout(); assert.equal(data.has(key), false); assert.equal(session.getSnapshot().user, null);
  await session.login('b@example.com','password');assert.equal(calls.length,2);
});
test("old restoration cannot overwrite a newer login", async () => {
  const stale = deferred(); const { session, data } = setup({ getCurrentUser: token => token === "old" ? stale.promise : Promise.resolve(identity("admin", 2)) });
  data.set(key, "old"); const restore = session.restore(); session.logout(); await session.login("new@example.com", "password");
  stale.resolve(identity("customer", 1)); await restore; assert.equal(session.getSnapshot().user.user_id, 2); assert.equal(data.get(key), "token");
});
test("cancelled requests cannot alter a newer account", async () => {
  const old = deferred(); let count = 0;
  const { session } = setup({ loginUser: () => ++count === 1 ? old.promise : Promise.resolve({ access_token: "new" }) });
  const pending = session.login("a@example.com", "password"); session.logout(); await session.login("b@example.com", "password");
  old.resolve({ access_token: "old" }); await assert.rejects(pending); assert.equal(session.getSnapshot().token, "new");
});
test("invalid credentials, server, network and timeout failures leave no session", async () => {
  for (const error of [{ response: { status: 401 } }, { response: { status: 403 } }, { response: { status: 500 } }, { code: "ECONNABORTED" }, new Error("Network")]) {
    const { session, data } = setup({ loginUser: async () => { throw error; } });
    await assert.rejects(session.login("test@example.com", "password")); assert.equal(data.size, 0); assert.equal(session.getSnapshot().loading, false);
  }
});
test("missing tokens, identity failures and storage errors never authenticate", async () => {
  const sessions = [setup({ loginUser: async () => ({}) }).session, setup({ getCurrentUser: async () => { throw new Error("Failed"); } }).session,
    setup({ storage: () => ({ removeItem() {}, setItem() { throw new Error("Storage"); } }) }).session];
  for (const session of sessions) { await assert.rejects(session.login("test@example.com", "password")); assert.equal(session.getSnapshot().user, null); }
  assert.throws(() => validateIdentity(null));
});
test("login errors do not reveal backend account existence or internal details", () => {
  for (const status of [401, 403, 422, 429, 500]) assert.ok(!getLoginErrorMessage({ response: { status, data: { detail: "secret database error" } } }).includes("secret"));
  assert.match(getLoginErrorMessage({ response: { status: 401 } }), /Invalid email or password/);
  assert.match(getLoginErrorMessage({ code: "ECONNABORTED" }), /timed out/);
});
test("existing approval flow and backend restrictions are preserved", async () => {
  const dashboard = await readFile(new URL('../src/pages/shopOwner/ShopOwnerDashboard.jsx', import.meta.url), 'utf8');
  assert.ok(dashboard.includes('to="/shop-owner/business/register"'));
  assert.ok(dashboard.includes('Business approval required')); assert.ok(dashboard.includes('!isApproved'));
  const dependency = await readFile(new URL('../../backend/app/core/auth_dependencies.py', import.meta.url), 'utf8');
  assert.ok(dependency.includes('user.account_status != "active"')); assert.ok(dependency.includes('current_user.platform_role not in allowed'));
  const form = await readFile(new URL('../src/pages/auth/LoginForm.jsx', import.meta.url), 'utf8');
  assert.ok(form.includes('if (submitting.current) return')); assert.ok(form.includes('required'));
  const provider = await readFile(new URL('../src/context/AuthContext.jsx', import.meta.url), 'utf8');
  assert.ok(provider.includes('session-expired')); assert.ok(provider.includes('key={state.token || "signed-out"}'));
});

test("expired-session event clears identity and provides a sign-in notice", async () => {
  const { session, data } = setup(); await session.login("test@example.com", "password"); session.expire();
  assert.equal(data.has(key), false); assert.equal(session.getSnapshot().user, null); assert.match(session.getSnapshot().notice, /session expired/);
  await session.login("test@example.com", "password"); assert.equal(session.getSnapshot().notice, undefined);
});
test("expired refresh shows a notice and failed identity verification differs from incorrect credentials", async () => {
  const { session, data } = setup({ getCurrentUser: async () => { throw { response: { status: 401 } }; } });
  data.set(key, "expired"); await session.restore(); assert.match(session.getSnapshot().notice, /session expired/);
  let failure; try { await session.login("test@example.com", "password"); } catch (error) { failure = error; }
  assert.equal(failure.authStage, "identity"); assert.match(getLoginErrorMessage(failure), /could not be verified/);
  assert.match(getLoginErrorMessage({ response: { status: 401 } }), /Invalid email or password/);
});
test("identity network, timeout and invalid-role failures have separate helpful messages", () => {
  assert.match(getLoginErrorMessage({ authStage: "identity", code: "ERR_NETWORK" }), /verify your account/);
  assert.match(getLoginErrorMessage({ authStage: "identity", code: "ECONNABORTED" }), /verification timed out/);
  assert.match(getLoginErrorMessage({ authStage: "identity", code: "INVALID_IDENTITY" }), /account role/);
  assert.match(getLoginErrorMessage({ code: "ERR_NETWORK" }), /backend server is running/);
});

test("unsupported login role keys always resolve to the unified login URL", () => {
  for (const role of [undefined, null, "unknown", "toString", "constructor", "__proto__"]) assert.equal(getLoginPath(role), "/login");
});

test('shared browser account blocks a second tab and logout synchronizes through restore', async()=>{
  const data=new Map(),storage=()=>({getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)});
  let calls=0;
  const options={storage,loginUser:async()=>{calls++;return {access_token:'shared'};},getCurrentUser:async()=>identity('driver',7)};
  const first=createAuthSession(options),second=createAuthSession(options);
  await first.login('one@example.com','password');
  await assert.rejects(second.login('two@example.com','password'),{code:'BROWSER_ALREADY_SIGNED_IN'});
  assert.equal(calls,1);await second.restore();assert.equal(second.getSnapshot().user.user_id,7);
  first.logout();await second.restore();assert.equal(second.getSnapshot().user,null);
});

test('serialized cross-tab sign-ins issue only one login and preserve the winning token',async()=>{
  const data=new Map(),storage=()=>({getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)});
  let tail=Promise.resolve(),calls=0;
  const withLoginLock=operation=>{const work=tail.then(operation);tail=work.catch(()=>{});return work;};
  const options={storage,withLoginLock,loginUser:async()=>({access_token:'winner-'+(++calls)}),getCurrentUser:async()=>identity()};
  const first=createAuthSession(options),second=createAuthSession(options);
  const results=await Promise.allSettled([first.login('one@example.com','password'),second.login('two@example.com','password')]);
  assert.equal(results.filter(r=>r.status==='fulfilled').length,1);assert.equal(calls,1);assert.equal(data.get(key),'winner-1');
});

test('stale restoration cannot clear a newer shared token on error',async()=>{
  const failed=deferred();const {session,data}=setup({getCurrentUser:()=>failed.promise});
  data.set(key,'old');const work=session.restore();data.set(key,'new');failed.reject({response:{status:401}});await work;
  assert.equal(data.get(key),'new');assert.equal(session.getSnapshot().user,null);
});
