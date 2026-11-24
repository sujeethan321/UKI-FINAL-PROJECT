import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { createServer } from "vite";
import { subscriptionDisplay, formatPlanPrice } from "../src/utils/subscription.js";

test("trial display expires at the exact boundary and preserves active paid plans", () => {
  const end = Date.parse("2028-02-29T12:00:00Z");
  const trial = { trial_active: true, effective_plan: "PRO", status: "TRIALING", trial_ends_at: new Date(end).toISOString() };
  assert.equal(subscriptionDisplay(trial, end - 1).plan, "PRO");
  assert.equal(subscriptionDisplay(trial, end).plan, "FREE");
  assert.equal(subscriptionDisplay(trial, end).upgrade, true);
  assert.equal(subscriptionDisplay(trial, end - 86400001).days, 2);
  assert.equal(subscriptionDisplay({ ...trial, trial_active: false, status: "ACTIVE", effective_plan: "BUSINESS" }, end).plan, "BUSINESS");
});

test("plan prices use the exact server minor-unit amounts", () => {
  for (const [minor, expected] of [[0, "LKR 0"], [49900, "LKR 499"], [499000, "LKR 4,990"], [129900, "LKR 1,299"], [1299000, "LKR 12,990"], [49901, "LKR 499.01"]]) {
    assert.equal(formatPlanPrice(minor), expected);
  }
  for (const invalid of [NaN, 1.5, -1, Infinity, "49900"]) assert.equal(formatPlanPrice(invalid), "—");
});

test("subscription React views preserve business selection, price toggles and disabled payment boundary", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { default: SubscriptionBilling, SubscriptionBillingView: View } = await server.ssrLoadModule("/src/pages/shopOwner/SubscriptionBilling.jsx");
    const { createAppI18n } = await server.ssrLoadModule("/src/i18n/index.js");
    const plans = [{ plan: "FREE", monthly_minor: 0, yearly_minor: 0 }, { plan: "PRO", monthly_minor: 49900, yearly_minor: 499000 }, { plan: "BUSINESS", monthly_minor: 129900, yearly_minor: 1299000 }];
    const data = { business_id: 10, effective_plan: "PRO", status: "TRIALING", trial_active: true,
      trial_ends_at: new Date(Date.now() + 86400000 * 5).toISOString(), payment_configured: false };
    const props = { businesses: [{ business_id: 10, business_name: "Synthetic Shop" }, { business_id: 30, business_name: "Second Synthetic Shop" }], businessId: 10, data, plans,
      onBusiness() {}, onInterval() {}, onRetry() {} };
    const render = (extra = {}, language = "en") => renderToStaticMarkup(h(I18nextProvider, { i18n: createAppI18n({ language }) }, h(MemoryRouter, null, h(View, { ...props, ...extra }))));
    await t.test("direct Checkout return renders before business context has loaded", () => {
      for (const query of ["success", "cancel"]) {
        const html = renderToStaticMarkup(h(I18nextProvider, { i18n: createAppI18n() },
          h(MemoryRouter, { initialEntries: [`/shop-owner/subscription?business_id=1&checkout=${query}`] },
            h(SubscriptionBilling))));
        assert.ok(html.includes("Subscription &amp; Billing"));
        assert.ok(html.includes("Register a business"));
        assert.ok(!html.includes("Active subscription"));
      }
    });
    await t.test("current plan, free trial, expiry, pricing and comparison remain truthful", () => {
      const html = render();
      for (const text of ["Subscription &amp; Billing", "Synthetic Shop", "Second Synthetic Shop", "Your free Pro trial is active", "Sri Lanka time", "No card required. No automatic charge.", "LKR 499", "LKR 1,299", "Compare plan features", "Payment integration not configured", "Payment &amp; invoice history"])
        assert.ok(html.includes(text), text);
      assert.match(html, /aria-pressed="true">Monthly/);
      assert.match(html, /<button[^>]*disabled=""[^>]*>Upgrade/);
      assert.match(html, /<select[^>]*>[^]*value="10" selected=""/);
      assert.ok(!html.includes("https://checkout.stripe.com"));
    });
    await t.test("yearly toggle renders the exact approved annual prices", () => {
      const html = render({ interval: "year" });
      assert.ok(html.includes("LKR 4,990"));
      assert.ok(html.includes("LKR 12,990"));
      assert.match(html, /aria-pressed="true">Yearly/);
    });
    await t.test("return queries and selected price never override the backend effective plan", () => {
      const free = { ...data, effective_plan: 'FREE', status: 'FREE', trial_active: false,
        payment_configured: true, checkout_available: true };
      for (const checkoutReturn of ['success', 'cancelled']) {
        const html = render({ data: free, checkoutReturn });
        assert.match(html, /Current plan<\/p><h3>Free<\/h3>/);
        assert.ok(!html.includes('Active subscription'));
      }
      assert.ok(render({ data: free, checkoutReturn: 'cancelled' }).includes('No plan change was confirmed'));
      const paid = render({ data: { ...free, effective_plan: 'PRO', status: 'ACTIVE' } });
      assert.match(paid, /Current plan<\/p><h3>Pro<\/h3>/);
      assert.ok(paid.includes('Active subscription'));
    });
    await t.test('configured Sandbox enables explicit billing actions without trusting return parameters', () => {
      const configured = { ...data, effective_plan: 'FREE', status: 'FREE', trial_active: false,
        payment_configured: true, checkout_available: true, portal_available: false };
      const html = render({ data: configured, checkoutReturn: 'success' });
      assert.ok(html.includes('Stripe Sandbox'));
      assert.ok(html.includes('Payment verification is pending'));
      assert.match(html, /<button[^>]*aria-describedby="subscription-payment-note"[^>]*>Upgrade/);
      assert.ok(!html.includes('Active subscription'));
      const error = render({ data: { ...configured, payment_failed: true }, billingError: true, busy: true });
      assert.ok(error.includes('Payment failed.'));
      assert.ok(error.includes('Reconcile the existing attempt'));
      assert.match(error, /<button[^>]*disabled=""[^>]*>Upgrade/);
      const calls = [];
      function CaptureBilling() {
        const tree = View({ ...props, data: configured, onCheckout: plan => calls.push(plan),
          onPortal: () => calls.push('portal'), onReconcile: () => calls.push('reconcile') });
        function visit(node) {
          if (!node || typeof node !== 'object') return;
          if (node.type === 'button' && !node.props.disabled && node.props.onClick &&
            ['Upgrade', 'Reconcile pending Checkout'].includes(node.props.children)) node.props.onClick();
          for (const child of [node.props?.children].flat(Infinity)) visit(child);
        }
        visit(tree); return tree;
      }
      renderToStaticMarkup(h(I18nextProvider, { i18n: createAppI18n() }, h(MemoryRouter, null, h(CaptureBilling))));
      assert.deepEqual(calls, ['PRO', 'BUSINESS', 'reconcile']);
    });
    await t.test("existing interaction handlers receive only the selected business and interval", () => {
      const calls = [];
      function visit(node) {
        if (!node || typeof node !== "object") return;
        if (node.props?.value === 10 && node.props.onChange) node.props.onChange({ target: { value: "30" } });
        if (node.type === "button" && node.props["aria-pressed"] === false && node.props.children === "Yearly") node.props.onClick();
        for (const child of [node.props?.children].flat(Infinity)) visit(child);
      }
      function Capture() {
        const tree = View({ ...props, onBusiness: value => calls.push(["business", value]), onInterval: value => calls.push(["interval", value]) });
        visit(tree);
        return tree;
      }
      renderToStaticMarkup(h(I18nextProvider, { i18n: createAppI18n() }, h(MemoryRouter, null, h(Capture))));
      assert.deepEqual(calls, [["business", 30], ["interval", "year"]]);
    });
    await t.test("expired trial shows Free and records/repayment preservation", () => {
      const html = render({ data: { ...data, status: "EXPIRED", effective_plan: "FREE", trial_active: false, upgrade_required: true, trial_ends_at: "2020-01-01T00:00:00Z" } });
      assert.ok(html.includes("Your Pro trial has ended"));
      assert.ok(html.includes("Your records and repayment access are preserved."));
      assert.ok(html.includes("Free access — no recurring payment."));
    });
    await t.test("loading, unavailable and no-business states never invent a plan", () => {
      assert.ok(render({ data: undefined, loading: true }).includes("Loading subscription..."));
      const failed = render({ data: undefined, error: true });
      assert.ok(failed.includes('role="alert"')); assert.ok(failed.includes("Retry"));
      assert.ok(!failed.includes("LKR 499"));
      assert.ok(render({ businesses: [], businessId: undefined, data: undefined }).includes("Register a business"));
    });
    await t.test("English, Tamil and Sinhala subscription strings are complete Unicode", async () => {
      const source = await readFile(new URL("../src/pages/shopOwner/SubscriptionBilling.jsx", import.meta.url), "utf8");
      const summary = await readFile(new URL("../src/components/shopOwner/SubscriptionSummary.jsx", import.meta.url), "utf8");
      const labels = [...(source + summary).matchAll(/tr\("([^"]+)"/g)].map(match => match[1]);
      for (const language of ["en", "ta", "si"]) {
        const catalog = JSON.parse(await readFile(new URL(`../src/i18n/locales/application.${language}.json`, import.meta.url), "utf8"));
        for (const label of labels) assert.ok(catalog[label], `${language}: ${label}`);
        for (const label of ["Subscription & Billing", "Payment integration not configured", "Your free Pro trial is active"]) {
          assert.ok(!catalog[label].includes("?"));
          if (language !== "en") assert.notEqual(catalog[label], label);
        }
        const html = render({}, language);
        assert.ok(html.includes(catalog["Payment integration not configured"]));
      }
    });
    await t.test("responsive, accessible CSS and isolated request contracts", async () => {
      const css = await readFile(new URL("../src/pages/shopOwner/subscription.css", import.meta.url), "utf8");
      assert.ok(css.includes("grid-template-columns:repeat(3"));
      assert.ok(css.includes("grid-template-columns:1fr"));
      assert.ok(css.includes(":focus-visible"));
      assert.ok(css.includes("overflow:auto"));
      const service = await readFile(new URL("../src/services/subscriptionService.js", import.meta.url), "utf8");
      assert.ok(service.includes("business_id: businessId"));
      assert.ok(service.includes("'/subscriptions/checkout'"));
      assert.ok(!service.includes('price_id'));
      const app = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
      assert.ok(app.includes('<Route path="subscription" element={<SubscriptionBilling />} />'));
    });
  } finally { await server.close(); }
});
