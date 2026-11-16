import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { createServer } from "vite";
import { parse } from "espree";
import { fixtures } from "./fixtures/customerDashboardFixtures.js";
import { driverFixtures } from "./fixtures/driverDashboardFixtures.js";
import { overviewFixture, activityFixture } from "./fixtures/adminDashboardFixtures.js";
import { createRegistrationController, registrationPayload } from "../src/utils/registration.js";
import { parseCustomerResponse } from "../src/utils/customerDashboard.js";

const actions = { start() {}, load() {} };
const section = data => ({ data, loading: false, error: "" });

test("authentication and four-role multilingual demonstration", async suite => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { createAppI18n, resources } = await server.ssrLoadModule("/src/i18n/index.js");
    const instance = createAppI18n();
    const { AuthContext } = await server.ssrLoadModule("/src/context/AuthContext.jsx");
    const { default: LoginForm } = await server.ssrLoadModule("/src/pages/auth/LoginForm.jsx");
    const { default: RegistrationForm } = await server.ssrLoadModule("/src/pages/auth/RegistrationForm.jsx");
    const { default: BrandPanel } = await server.ssrLoadModule("/src/pages/auth/LoginBrandPanel.jsx");
    const { default: OwnerDashboard } = await server.ssrLoadModule("/src/pages/shopOwner/ShopOwnerDashboard.jsx");
    const { default: OwnerOverview } = await server.ssrLoadModule("/src/components/shopOwner/OverviewCards.jsx");
    const { CustomerDashboardView } = await server.ssrLoadModule("/src/pages/customer/CustomerDashboard.jsx");
    const { DriverDashboardView } = await server.ssrLoadModule("/src/pages/driver/DriverDashboard.jsx");
    const { AdminDashboardView } = await server.ssrLoadModule("/src/pages/admin/AdminDashboard.jsx");
    const { parseAdminOverview, parseAdminActivity } = await server.ssrLoadModule("/src/utils/adminDashboard.js");
    const { useAppTranslation } = await server.ssrLoadModule("/src/i18n/useAppTranslation.js");
    const auth = { user: null, loading: false, isAuthenticated: false, login() {}, logout() {}, notice: "" };
    const render = (component, props = {}, userContext = auth) => renderToStaticMarkup(createElement(I18nextProvider, { i18n: instance }, createElement(AuthContext.Provider, { value: userContext }, createElement(MemoryRouter, null, createElement(component, props)))));
    const tr = key => instance.t(key, { ns: "application", keySeparator: false, nsSeparator: false });

    await suite.test("application resources are complete, distinct and use valid Unicode", () => {
      const keys = Object.keys(resources.en.application);
      for (const lang of ["ta", "si"]) {
        assert.deepEqual(Object.keys(resources[lang].application), keys);
        for (const key of keys) {
          const value = resources[lang].application[key];
          assert.ok(value.trim(), `${lang}: ${key}`);
          assert.ok(!value.includes("\uFFFD"), key);
          assert.deepEqual(value.match(/{{\w+}}/g)?.sort(), key.match(/{{\w+}}/g)?.sort(), key);
        }
        for (const key of ["Password", "Repayments", "Outstanding", "Overdue Amount", "Credit limit:"]) {
          assert.notEqual(resources[lang].application[key], key);
        }
      }
    });

    for (const lang of ["en", "ta", "si"]) {
      await suite.test(`${lang}: login labels, show-password accessibility and secure registration return`, async () => {
        await instance.changeLanguage(lang);
        const html = render(LoginForm, { joinReturnTo: "/join/" + "a".repeat(32) });
        for (const key of ["Welcome Back", "Email Address", "Password", "Show password", "Log In"]) assert.ok(html.includes(tr(key)), key);
        assert.ok(html.includes('type="password"'));
        assert.ok(html.includes('autoComplete="current-password"'));
        assert.ok(html.includes('href="/register/customer"'));
        const brand = render(BrandPanel);
        assert.ok(brand.includes('value="en"') && brand.includes('value="ta"') && brand.includes('value="si"'));
        assert.ok(brand.includes(tr("Connect with Confidence")));
      });

      await suite.test(`${lang}: registration role values, form values and constraints stay unchanged`, async () => {
        await instance.changeLanguage(lang);
        let requests = 0;
        for (const role of ["shop-owner", "customer", "driver"]) {
          const controller = createRegistrationController({ role, services: { [role]: () => { requests++; } }, onSuccess() {}, errorMessage: () => "" });
          controller.update("full_name", "Dashboard"); // Must remain business/user data, even if a translation key.
          controller.update("email", "synthetic@example.invalid");
          controller.update("password", "SyntheticFormValue-42");
          controller.update("confirmPassword", "SyntheticFormValue-42");
          const before = controller.getSnapshot();
          for (const switched of ["ta", "si", "en", lang]) {
            await instance.changeLanguage(switched);
            const html = render(RegistrationForm, { controller });
            assert.ok(html.includes('value="Dashboard"'));
            assert.ok(html.includes('value="synthetic@example.invalid"'));
            assert.ok(html.includes('value="SyntheticFormValue-42"'));
            assert.ok(html.includes('value="' + role + '"'));
            assert.ok(html.includes('minLength="12"') && html.includes('maxLength="128"'));
            assert.ok(html.includes('href="/login"'));
            assert.ok(html.includes(tr("Confirm Password *")));
            assert.equal(controller.getSnapshot(), before);
            assert.equal(registrationPayload(before.form, before.confirmPassword).preferred_language, "en");
          }
        }
        assert.equal(requests, 0);
      });

      await suite.test(`${lang}: all four dashboards translate without translating records or amounts`, async () => {
        await instance.changeLanguage(lang);
        assert.ok(render(OwnerDashboard).includes(tr("Loading your business information...")));
        assert.ok(render(OwnerOverview, { summary: { total_outstanding: "70.10", collected_today: "30.10", overdue_amount: "0.00" } }).includes(tr("Collected Today")));
        const customer = { authError: "", ...Object.fromEntries(Object.entries(fixtures()).map(([key, data]) => [key, section(parseCustomerResponse(key, data))])) };
        customer.shops.data.items[0].business_name = "Dashboard";
        const html = render(CustomerDashboardView, { state: customer, actions, displayName: "Dashboard" });
        assert.ok(html.includes(tr("My Credit Accounts")));
        assert.ok(html.includes(tr("Overdue Amount")));
        assert.ok(html.includes("LKR 100.25") && html.includes("LKR 1,000.00"));
        assert.ok(html.includes(">Dashboard</h3>"));
        assert.ok(html.includes('href="/customer/credit/8"'));
        const driver = { authError: "", ...Object.fromEntries(Object.entries(driverFixtures()).map(([key, data]) => [key, section(data)])) };
        const driverHtml = render(DriverDashboardView, { state: driver, actions, displayName: "Driver A" });
        for (const key of ["Driver Dashboard", "Completed Deliveries", "Assigned", "In transit"]) assert.ok(driverHtml.includes(tr(key)), key);
        assert.ok(driverHtml.includes("Assigned shop") && driverHtml.includes("DR-test-one"));
        const adminHtml = render(AdminDashboardView, { state: { authError: "", overview: section(parseAdminOverview(overviewFixture())), activity: section(parseAdminActivity(activityFixture())) }, actions });
        for (const key of ["Platform Dashboard", "Total Customers", "Driver approved", "Business rejected"]) assert.ok(adminHtml.includes(tr(key)), key);
        assert.ok(!adminHtml.includes("PRIVATE-NOTE") && !adminHtml.includes("PRIVATE-REASON"));
      });

      await suite.test(`${lang}: role sidebar destinations and mobile menu semantics stay intact`, async () => {
        await instance.changeLanguage(lang);
        for (const role of ["shopOwner", "customer", "driver", "admin"]) {
          const name = { shopOwner: "ShopOwner", customer: "Customer", driver: "Driver", admin: "Admin" }[role];
          const { default: Sidebar } = await server.ssrLoadModule(`/src/components/${role}/${name}Sidebar.jsx`);
          const html = render(Sidebar);
          const route = role === "shopOwner" ? "shop-owner" : role;
          assert.ok(html.includes(`href="/${route}/dashboard"`));
          assert.ok(html.includes(tr("Dashboard")));
          if (role === "shopOwner") {
            assert.ok(html.includes('aria-expanded="false"'));
            assert.ok(html.includes(tr("Open shop owner menu")));
          } else assert.ok(html.includes("<dialog"));
        }
      });

      await suite.test(`${lang}: session errors, loading and retry labels translate without exposing stale records`, async () => {
        await instance.changeLanguage(lang);
        const error = "Your session has expired. Please sign in again.";
        const customer = { authError: error, ...Object.fromEntries(Object.entries(fixtures()).map(([key, data]) => [key, section(parseCustomerResponse(key, data))])) };
        const denied = render(CustomerDashboardView, { state: customer, actions, displayName: "Demo" });
        assert.ok(denied.includes(tr(error)));
        assert.ok(!denied.includes("LKR 100.25"));
        customer.authError = "";
        customer.summary = { data: null, loading: true, error: "" };
        customer.accounts = { data: null, loading: false, error: "The customer service is unavailable. Please retry." };
        const loading = render(CustomerDashboardView, { state: customer, actions, displayName: "Demo" });
        assert.ok(loading.includes(tr("Loading your account summary...")));
        assert.ok(loading.includes(tr("The customer service is unavailable. Please retry.")));
        const admin = render(AdminDashboardView, { state: { authError: error, overview: section(null), activity: section(null) }, actions });
        assert.ok(admin.includes(tr(error)));
      });
    }

    await suite.test("known validation messages translate; unknown server errors safely retain their text", async () => {
      for (const lang of ["ta", "si"]) {
        await instance.changeLanguage(lang);
        const controller = createRegistrationController({ services: {}, onSuccess() {}, errorMessage: () => "" });
        await controller.submit();
        assert.ok(render(RegistrationForm, { controller }).includes(tr(controller.getSnapshot().error)));
        function Probe() { const { tr: translate } = useAppTranslation(); return createElement("p", null, translate("Unmapped safe server message.")); }
        assert.ok(render(Probe).includes("Unmapped safe server message."));
        instance.addResource("en", "application", "Sprint fallback probe", "English fallback preserved");
        assert.equal(tr("Sprint fallback probe"), "English fallback preserved");
      }
    });

    await suite.test("translated component literals resolve; auth, API identifiers and form controllers remain independent of locale", async () => {
      const files = ["pages/auth/LoginForm.jsx", "pages/auth/RegistrationForm.jsx", "pages/auth/LoginBrandPanel.jsx", "pages/shopOwner/ShopOwnerDashboard.jsx", "pages/customer/CustomerDashboard.jsx", "pages/driver/DriverDashboard.jsx", "pages/admin/AdminDashboard.jsx", "components/shopOwner/ShopOwnerHeader.jsx", "components/shopOwner/OverviewCards.jsx", "components/shopOwner/RecentCreditTransactions.jsx", "components/shopOwner/NeedsAttention.jsx", "components/shopOwner/QuickActions.jsx", "components/customer/CustomerCreditOverview.jsx", "components/customer/CustomerRecentOrders.jsx", "components/customer/CustomerLinkAcceptance.jsx", "components/customer/CustomerData.jsx", "components/driver/DriverProfileForm.jsx", "pages/driver/AvailableJobs.jsx", "components/notifications/NotificationBell.jsx"];
      for (const file of files) {
        const source = await readFile(new URL("../src/" + file, import.meta.url), "utf8");
        const tree = parse(source, { ecmaVersion: "latest", sourceType: "module", ecmaFeatures: { jsx: true } });
        function visit(node) {
          if (!node || typeof node !== "object") return;
          if (node.type === "CallExpression" && node.callee.name === "tr" && typeof node.arguments[0]?.value === "string") {
            const key = node.arguments[0].value;
            for (const lang of ["en", "ta", "si"]) assert.ok(Object.hasOwn(resources[lang].application, key), `${lang}: ${file}: ${key}`);
          }
          for (const value of Object.values(node)) if (Array.isArray(value)) value.forEach(visit); else if (value && typeof value === "object") visit(value);
        }
        visit(tree);
        assert.ok(!/key=\{[^}]*i18n\.language/.test(source), file);
      }
    });
  } finally { await server.close(); }
});
