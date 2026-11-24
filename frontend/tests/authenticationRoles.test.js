import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement, useContext } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { createServer } from "vite";
import { createRegistrationController, registrationPayload, publicRegistrationRoles } from "../src/utils/registration.js";
import { getDashboardPath, getLoginPath } from "../src/utils/roleRoutes.js";

const driverFixture = () => ({ vehicle_type: 'Bike', registration_reference: 'FICTIONAL-123',
  driving_licence: new File(['fictional'], 'licence.png', { type: 'image/png' }),
  vehicle_ownership_proof: new File(['fictional'], 'ownership.pdf', { type: 'application/pdf' }) });

test("registration cards and unified login", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { AuthContext, AuthProvider } = await server.ssrLoadModule("/src/context/AuthContext.jsx");
    const { default: RegisterPage } = await server.ssrLoadModule("/src/pages/auth/RegisterPage.jsx");
    const { default: LoginPage } = await server.ssrLoadModule("/src/pages/auth/LoginPage.jsx");
    const renderRegistration = role => renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: ["/register/" + role] }, createElement(Routes, null, createElement(Route, { path: "/register/:role", element: createElement(RegisterPage) }))));
    for (const role of ["shop-owner", "customer", "driver"]) {
      await t.test(role + " registration selects exactly its existing form", () => {
        const html = renderRegistration(role);
        assert.equal((html.match(/type="radio"/g) || []).length, 3);
        const radios = html.match(/<input[^>]+type="radio"[^>]*>/g);
        assert.equal(radios.filter(input => input.includes('checked=""')).length, 1);
        assert.ok(radios.find(input => input.includes('checked=""')).includes('value="' + role + '"'));
        for (const description of ["Manage customers and credit.", "Shop and manage credit.", "Deliver orders and earn."]) assert.ok(html.includes(description));
        assert.ok(html.indexOf("registration-role") < html.indexOf('id="full_name"'));
        assert.ok(!html.includes('value="admin"'));
        assert.match(html, /minLength="12"/);
        assert.match(html, /id="password"[^>]*aria-describedby="registration-password-help"/);
        assert.match(html, /id="registration-password-help"[^>]*>Use 12 to 128 characters\./);
        assert.match(html, /name="preferred_language"/);
        assert.match(html, /href="\/login"/);
      });
    }
    await t.test("one credential-only login page regardless of legacy role URL", () => {
      for (const role of ["shop-owner", "customer", "driver", "admin"]) {
        const html = renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: ["/login/" + role] }, createElement(AuthContext.Provider, { value: {} }, createElement(LoginPage))));
        assert.match(html, /Welcome Back/); assert.match(html, /type="email"/); assert.match(html, /type="password"/);
        assert.ok(!html.includes('type="radio"')); assert.ok(!html.includes("Choose another role"));
      }
    });
    await t.test("unified /register opens directly with a single default role", async () => {
      const html = renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: ["/register"] }, createElement(Routes, null, createElement(Route, { path: "/register", element: createElement(RegisterPage) }))));
      const radios = html.match(/<input[^>]+type="radio"[^>]*>/g);
      assert.equal(radios.length, 3);
      assert.equal(radios.filter(input => input.includes('checked=""')).length, 1);
      assert.ok(radios.find(input => input.includes('checked=""')).includes('value="shop-owner"'));
      const app = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
      assert.ok(app.includes('<Route path="/register" element={<RegisterPage />} />'));
      assert.ok(!app.includes('to="/register/shop-owner"'));
      assert.ok(html.includes('href="/login"'));
    });
    await t.test("selected role state renders existing styling, native radios and locked submission", async () => {
      const { default: Form } = await server.ssrLoadModule("/src/pages/auth/RegistrationForm.jsx");
      let finish;
      const controller = createRegistrationController({ services: { driver: () => new Promise(resolve => { finish = resolve; }) }, onSuccess() {}, errorMessage: () => "Failed" });
      const render = () => renderToStaticMarkup(createElement(MemoryRouter, null, createElement(Form, { controller })));
      for (const role of publicRegistrationRoles) {
        controller.selectRole(role);
        const html = render();
        const selected = html.match(/<input[^>]+type="radio"[^>]*>/g).filter(input => input.includes('checked=""'));
        assert.equal(selected.length, 1); assert.ok(selected[0].includes('value="' + role + '"'));
        for (const style of ['peer-checked:border-[#12B8A6]', 'peer-checked:bg-[#F0FCF9]', 'rounded-full bg-[#12B8A6]', 'peer-focus-visible:ring-2', 'grid-cols-1', 'min-[420px]:grid-cols-3']) assert.ok(html.includes(style));
        assert.ok(!html.includes('value="admin"'));
      }
      for (const [name, value] of Object.entries(validRegistration)) controller.update(name, value);
      for (const [name, value] of Object.entries(driverFixture())) controller.update(name, value);
      controller.update("confirmPassword", validRegistration.password);
      const submission = controller.submit(); await Promise.resolve();
      const locked = render();
      assert.match(locked, /<fieldset disabled=""/);
      for (const element of locked.matchAll(/<(input|select)[^>]*>/g)) {
        if (!element[0].includes('type="radio"')) assert.ok(element[0].includes('disabled=""'));
      }
      assert.ok(locked.includes('Creating Account...'));
      finish({ role: "driver" }); await submission;
      assert.ok(!renderRegistration('admin').includes('<form'));
    });
    await t.test("landing and login entry links use unified registration", async () => {
      const { default: Landing } = await server.ssrLoadModule("/src/pages/landing/LandingPage.jsx");
      const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(Landing)));
      assert.match(html, /class="landing-button primary" href="\/register"[^>]*>Get Started/);
      const login = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(AuthContext.Provider, { value: {} }, createElement(LoginPage))));
      assert.ok(login.includes('href="/register"')); assert.ok(!login.includes('type="radio"'));
      const page = await readFile(new URL("../src/pages/auth/RegisterPage.jsx", import.meta.url), "utf8");
      assert.ok(page.includes('navigate("/login", { replace: true, state: { registrationSuccess: true } })'));
      assert.ok(!page.includes('key={role}'));
    });
    const { default: api, setAuthTokenReader } = await server.ssrLoadModule("/src/services/api.js");
    const previousAdapter = api.defaults.adapter;
    const previousStorage = globalThis.localStorage;
    try {
      let capturedAuth;
      function Probe() { capturedAuth = useContext(AuthContext); return null; }
      renderToStaticMarkup(createElement(AuthProvider, null, createElement(Probe)));
      for (const role of ["shop_owner", "customer", "driver", "admin"]) {
        await t.test("backend-verified " + role + " signs in without a selected role", async () => {
          const stored = new Map(); globalThis.localStorage = { setItem: (k,v) => stored.set(k,v), removeItem: k => stored.delete(k), getItem: k => stored.get(k) };
          capturedAuth.logout();
          const calls = [];
          api.defaults.adapter = async config => { calls.push(config); return { data: config.url === "/auth/login" ? { access_token: "isolated-test-token" } : { user_id: 1, account_status: "active", platform_role: role, full_name: "Test account" }, status: 200, statusText: "OK", headers: {}, config }; };
          const result = await capturedAuth.login(" TEST@EXAMPLE.COM ", "isolated-test-password");
          assert.equal(result.platform_role, role);
          assert.deepEqual(calls.map(c => c.url), ["/auth/login", "/auth/me"]);
          assert.equal(new URLSearchParams(calls[0].data).get("username"), "test@example.com");
          assert.equal(new URLSearchParams(calls[0].data).get("role"), null);
          assert.equal(calls[1].headers.Authorization, "Bearer isolated-test-token");
          assert.equal(stored.get("lankapex_access_token"), "isolated-test-token");
          assert.equal(getLoginPath(role), "/login");
          assert.equal(getDashboardPath(role), { shop_owner: "/shop-owner/dashboard", customer: "/customer/dashboard", driver: "/driver/dashboard", admin: "/admin/dashboard" }[role]);
        });
      }
      capturedAuth.logout();
      setAuthTokenReader(() => globalThis.localStorage?.getItem('lankapex_access_token') ?? null);
      await t.test("Axios expires only the active token and ignores stale-account failures", async () => {
        const previousWindow = globalThis.window;
        const stored = new Map([["lankapex_access_token", "current-fixture-token"]]);
        const events = [];
        globalThis.localStorage = { setItem: (k,v) => stored.set(k,v), removeItem: k => stored.delete(k), getItem: k => stored.get(k) };
        globalThis.window = { dispatchEvent: event => events.push(event.type) };
        api.defaults.adapter = async config => { throw { config, response: { status: 401 } }; };
        try {
          await assert.rejects(api.get("/auth/me", { headers: { Authorization: "Bearer previous-fixture-token" } }));
          assert.equal(stored.get("lankapex_access_token"), "current-fixture-token"); assert.equal(events.length, 0);
          await assert.rejects(api.get("/auth/me", { headers: { Authorization: "Bearer current-fixture-token" } }));
          assert.equal(stored.has("lankapex_access_token"), false); assert.deepEqual(events, ["lankapex:session-expired"]);
        } finally { if (previousWindow === undefined) delete globalThis.window; else globalThis.window = previousWindow; }
      });
      await t.test("throttling, other HTTP errors and timeouts preserve the active session", async () => {
        const previousWindow = globalThis.window;
        const stored = new Map([["lankapex_access_token", "current-fixture-token"]]);
        const events = [];
        globalThis.localStorage = { setItem: (k,v) => stored.set(k,v), removeItem: k => stored.delete(k), getItem: k => stored.get(k) };
        globalThis.window = { dispatchEvent: event => events.push(event.type) };
        try {
          for (const status of [403, 409, 413, 422, 429, 500]) {
            api.defaults.adapter = async config => { throw { config, response: { status } }; };
            await assert.rejects(api.get("/auth/me"));
            assert.equal(stored.get("lankapex_access_token"), "current-fixture-token");
          }
          api.defaults.adapter = async config => { throw { config, code: "ECONNABORTED", message: "timeout" }; };
          await assert.rejects(api.get("/auth/me"));
          assert.deepEqual(events, []);
          assert.equal(stored.get("lankapex_access_token"), "current-fixture-token");
        } finally { if (previousWindow === undefined) delete globalThis.window; else globalThis.window = previousWindow; }
      });
      await t.test("basic role registration uses JSON and My Vehicle uses authenticated multipart", async () => {
        const service = await server.ssrLoadModule("/src/services/authService.js");
        const calls = [];
        api.defaults.adapter = async config => { calls.push(config); return { data: { id: 1 }, status: 200, statusText: "OK", headers: {}, config }; };
        const payload = { full_name: "Test User", email: "test@example.com", password: "isolated-test-password", phone: null, preferred_language: "en" };
        const documents = driverFixture();
        await service.registerShopOwner(payload); await service.registerCustomer(payload); await service.registerDriver(payload);
        assert.deepEqual(calls.map(c => c.url), ["/auth/register/shop-owner", "/auth/register/customer", "/auth/register/driver"]);
        for (const call of calls.slice(0, 2)) assert.deepEqual(JSON.parse(call.data), payload);
        assert.deepEqual(JSON.parse(calls[2].data),payload);
        const vehicleService=await server.ssrLoadModule('/src/services/driverDashboardService.js');
        await vehicleService.submitDriverProfile(documents);
        assert.equal(calls[3].url,'/driver/vehicle');
        assert.ok(calls[3].data instanceof FormData);
        assert.equal(calls[3].data.get('driving_licence').name,'licence.png');
        assert.equal(calls[3].data.get('vehicle_ownership_proof').type,'application/pdf');
      });
      await t.test("failed backend identity verification never persists a session", async () => {
        const stored = new Map(); globalThis.localStorage = { setItem: (k,v) => stored.set(k,v), removeItem: k => stored.delete(k), getItem: k => stored.get(k) };
        capturedAuth.logout();
        api.defaults.adapter = async config => { if (config.url === "/auth/me") throw new Error("Identity verification failed"); return { data: { access_token: "invalid-test-token" }, status: 200, statusText: "OK", headers: {}, config }; };
        await assert.rejects(capturedAuth.login("test@example.com", "isolated-test-password"), error => error.authStage === "identity");
        assert.equal(stored.size, 0);
      });
    } finally { api.defaults.adapter = previousAdapter; if (previousStorage === undefined) delete globalThis.localStorage; else globalThis.localStorage = previousStorage; }
    await t.test("login submits no role and redirects from returned identity", async () => {
      const source = await readFile(new URL("../src/pages/auth/LoginForm.jsx", import.meta.url), "utf8");
      const page = await readFile(new URL("../src/pages/auth/LoginPage.jsx", import.meta.url), "utf8");
      assert.ok(page.includes("loginDestination(user, joinReturnTo)"));
      assert.ok(page.includes("<Navigate to={destination} replace />"));
      assert.ok(!source.includes("backendRole"));
      const app = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
      assert.match(app, /path="\/login\/:role" element={<Navigate to="\/login" replace \/>}/);
    });
  } finally { await server.close(); }
});

const validRegistration = { full_name: " Test User ", email: " TEST@EXAMPLE.COM ", phone: "", password: "valid password 123", preferred_language: "en" };
function registrationSetup() {
  const calls = [], successes = [];
  let resolve;
  const response = new Promise(done => { resolve = done; });
  const services = Object.fromEntries(publicRegistrationRoles.map(role => [role, payload => { calls.push({ role, payload }); return response; }]));
  const controller = createRegistrationController({ services, onSuccess: value => successes.push(value), errorMessage: () => "Unable to register" });
  const fill = (patch = {}) => { for (const [name, value] of Object.entries({ ...validRegistration, ...patch })) controller.update(name, value); controller.update("confirmPassword", validRegistration.password); };
  return { controller, calls, successes, resolve, fill };
}
for (const role of ["shop-owner", "customer", "driver"]) {
  test("unified selection submits only " + role + " through its service", async () => {
    const { controller, calls, successes, resolve, fill } = registrationSetup();
    controller.selectRole(role); fill();
    const documents = role === 'driver' ? driverFixture() : {};
    for (const [name, value] of Object.entries(documents)) controller.update(name, value);
    const submission = controller.submit(); await Promise.resolve();
    assert.equal(calls.length, 1); assert.equal(calls[0].role, role);
    assert.deepEqual(calls[0].payload, { full_name: "Test User", email: "test@example.com", password: validRegistration.password, preferred_language: "en", phone: null });
    resolve({ role: role === "shop-owner" ? "shop_owner" : role, account_status: "active" });
    assert.equal(await submission, true); assert.equal(successes.length, 1);
    assert.equal(controller.getSnapshot().form.password, "");
  });
}
test("changing roles clears all fields, confirmation and errors before submission", async () => {
  const { controller, fill, calls } = registrationSetup(); fill();
  controller.update("confirmPassword", "wrong"); await controller.submit(); assert.ok(controller.getSnapshot().error);
  assert.equal(controller.selectRole("customer"), true);
  const state = controller.getSnapshot();
  assert.equal(state.role, "customer"); assert.equal(state.confirmPassword, ""); assert.equal(state.form.email, ""); assert.equal(state.form.password, ""); assert.equal(state.error, "");
  assert.equal(await controller.submit(), false); assert.equal(calls.length, 0);
});
test("duplicate registration shares one request and role/fields cannot change while pending", async () => {
  const { controller, calls, successes, resolve, fill } = registrationSetup(); fill();
  const first = controller.submit(), second = controller.submit(); assert.equal(first, second);
  assert.equal(controller.selectRole("driver"), false); controller.update("email", "other@example.com");
  assert.equal(controller.getSnapshot().form.email, validRegistration.email); assert.equal(controller.getSnapshot().loading, true);
  await Promise.resolve(); assert.equal(calls.length, 1);
  resolve({ role: "shop_owner" }); await first; assert.equal(successes.length, 1);
});
test("public roles cannot include admin, object keys or privilege fields", () => {
  const { controller, fill } = registrationSetup(); fill();
  for (const role of ["admin", "toString", "__proto__", "other"]) assert.equal(controller.selectRole(role), false);
  controller.update("platform_role", "admin"); controller.update("account_status", "active");
  const payload = registrationPayload(controller.getSnapshot().form, validRegistration.password);
  assert.ok(!Object.hasOwn(payload, "platform_role")); assert.ok(!Object.hasOwn(payload, "account_status"));
  assert.deepEqual(publicRegistrationRoles, ["shop-owner", "customer", "driver"]);
});
for (const patch of [{ full_name: " " }, { email: "invalid" }, { password: "short" }, { password: "x".repeat(129) }, { phone: "x".repeat(21) }, { preferred_language: "other" }]) {
  test("invalid registration never reaches API: " + Object.keys(patch)[0] + JSON.stringify(patch).length, async () => {
    const { controller, calls, fill } = registrationSetup(); fill(patch);
    assert.equal(await controller.submit(), false); assert.equal(calls.length, 0); assert.ok(controller.getSnapshot().error);
  });
}
test("registration failures retain the current form and never navigate", async () => {
  const controller = createRegistrationController({ services: { "shop-owner": async () => { throw new Error("Failure"); } }, onSuccess: () => assert.fail("must not navigate"), errorMessage: () => "Unable to register" });
  for (const [name, value] of Object.entries(validRegistration)) controller.update(name, value); controller.update("confirmPassword", validRegistration.password);
  assert.equal(await controller.submit(), false); assert.equal(controller.getSnapshot().loading, false);
  assert.equal(controller.getSnapshot().error, "Unable to register"); assert.equal(controller.getSnapshot().form.email, validRegistration.email);
});
test("leaving registration prevents late success from navigating another page", async () => {
  const { controller, successes, resolve, fill } = registrationSetup(); fill();
  const pending = controller.submit(); await Promise.resolve(); controller.cancel(); resolve({ role: "shop_owner" });
  assert.equal(await pending, false); assert.equal(successes.length, 0);
});
test("cancel before dispatch does not create an account", async () => {
  const { controller, calls, fill } = registrationSetup(); fill(); const pending = controller.submit(); controller.cancel();
  assert.equal(await pending, false); assert.equal(calls.length, 0);
});

test("cancelled registration can resume the same selected role without remaining locked", async () => {
  const { controller, fill, calls, resolve, successes } = registrationSetup();
  controller.selectRole("customer"); fill();
  const oldRequest = controller.submit(); await Promise.resolve();
  controller.cancel(); controller.resetRole("customer");
  assert.equal(controller.getSnapshot().loading, false);
  assert.equal(controller.getSnapshot().form.password, "");
  resolve({ role: "customer" }); assert.equal(await oldRequest, false);
  assert.equal(successes.length, 0);
  fill(); assert.equal(await controller.submit(), true);
  assert.equal(calls.length, 2); assert.equal(successes.length, 1);
});
