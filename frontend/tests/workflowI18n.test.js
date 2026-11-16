import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { createServer } from "vite";
import { parse } from "espree";
import { createCatalogueWorkflow } from "../src/utils/shopOwnerCatalogue.js";
import { createCustomerCatalogueWorkflow } from "../src/utils/customerCatalogue.js";
import { catalogueFixture } from "./fixtures/catalogueFixtures.js";
import { customerCatalogueFixture } from "./fixtures/customerCatalogueFixtures.js";
import { driverFixtures } from "./fixtures/driverDashboardFixtures.js";
const section = data => ({ data, loading: false, error: "" });
const noop = () => {};
const files = [
  "pages/shopOwner/ShopOwnerCustomers.jsx",
  "pages/shopOwner/AddCustomerModal.jsx",
  "pages/shopOwner/ManageCustomerModal.jsx",
  "pages/shopOwner/ShopOwnerCreditSales.jsx",
  "pages/shopOwner/ShopOwnerRepayments.jsx",
  "pages/shopOwner/ShopOwnerProducts.jsx",
  "pages/shopOwner/ShopOwnerDeliveries.jsx",
  "pages/shopOwner/FinancialDocuments.jsx",
  "components/shopOwner/OrderFulfilment.jsx",
  "components/shopOwner/CustomerLinkInvite.jsx",
  "components/shopOwner/TamilCreditSummary.jsx",
  "components/shopOwner/ShopQRCode.jsx",
  "components/shopOwner/PendingCustomerRequests.jsx",
  "pages/customer/CustomerCatalogue.jsx",
  "pages/customer/MyShops.jsx",
  "pages/customer/ShoppingCart.jsx",
  "pages/customer/CustomerCreditAccounts.jsx",
  "pages/customer/TransactionHistory.jsx",
  "pages/customer/CreditAccountDetails.jsx",
  "pages/customer/CreditStatement.jsx",
  "pages/customer/OrderHistory.jsx",
  "pages/customer/CustomerDeliveries.jsx",
  "components/customer/AddToCart.jsx",
  "components/customer/CustomerCartPreview.jsx",
  "components/customer/CustomerOrderTracking.jsx",
  "components/customer/CustomerJoinRequests.jsx",
  "pages/driver/DriverDeliveries.jsx",
  "pages/admin/AdminManagement.jsx",
  "components/delivery/DeliveryTimeline.jsx"
];
function walk(node, visitor, parent) {
  if (!node || typeof node !== "object") return;
  visitor(node, parent);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(child => walk(child, visitor, node));
    else if (value && typeof value === "object") walk(value, visitor, node);
  }
}
test("MVP workflow translations preserve records, drafts and API values", async suite => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { createAppI18n, resources } = await server.ssrLoadModule("/src/i18n/index.js");
    const i18n = createAppI18n();
    const render = (View, props) => renderToStaticMarkup(h(I18nextProvider, { i18n }, h(MemoryRouter, null, h(View, props))));
    const tr = key => i18n.t(key, { ns: "application", keySeparator: false, nsSeparator: false });
    const { ShopOwnerProductsView: Products } = await server.ssrLoadModule("/src/pages/shopOwner/ShopOwnerProducts.jsx");
    const { CustomerCatalogueView: Catalogue } = await server.ssrLoadModule("/src/pages/customer/CustomerCatalogue.jsx");
    const { CreditSalesView: Sales } = await server.ssrLoadModule("/src/pages/shopOwner/ShopOwnerCreditSales.jsx");
    const { RepaymentsView: Repayments } = await server.ssrLoadModule("/src/pages/shopOwner/ShopOwnerRepayments.jsx");
    const { DriverDeliveriesView: Deliveries } = await server.ssrLoadModule("/src/pages/driver/DriverDeliveries.jsx");
    const { ManagementConfirmation: Confirmation } = await server.ssrLoadModule("/src/pages/admin/AdminManagement.jsx");
    const { default: ManageCustomer } = await server.ssrLoadModule("/src/pages/shopOwner/ManageCustomerModal.jsx");
    const { ShoppingContext } = await server.ssrLoadModule("/src/context/ShoppingContext.js");
    const { default: Cart } = await server.ssrLoadModule("/src/pages/customer/ShoppingCart.jsx");
    const { MyShopsView } = await server.ssrLoadModule("/src/pages/customer/MyShops.jsx");
    const { OrderRecord } = await server.ssrLoadModule("/src/pages/customer/OrderHistory.jsx");
    const { default: Timeline } = await server.ssrLoadModule("/src/components/delivery/DeliveryTimeline.jsx");
    const f = catalogueFixture(), workflow = createCatalogueWorkflow(f.api, 7, f.store);
    await workflow.start(); await workflow.openProduct(31);
    workflow.edit("product", "name", "Dashboard");
    const cf = customerCatalogueFixture(), catalogue = createCustomerCatalogueWorkflow(cf.api, { businessId: 1 });
    await catalogue.start();
    const owner = {
      businesses: [{ business_id: 1, business_name: "Dashboard", approval_status: "approved" }], businessId: "1", customerId: "10",
      customers: [{ customer_id: 10, customer_name: "Products" }],
      details: { business_id: 1, customer: { business_id: 1, customer_id: 10, customer_name: "Products" },
        credit_account: { credit_account_id: 110, account_status: "active", credit_limit: "1000.00" },
        outstanding_balance: "70.10", advance_balance: "0.00", available_credit: "929.90", transactions: [] },
      contextLoading: false, customersLoading: false, detailsLoading: false, saving: false,
      contextError: "", customersError: "", detailsError: "", storageError: "", error: "", amount: "30.10", notes: "Dashboard", success: null, uncertain: false,
      paymentMethod: "cash", reference: ""
    };
    const row = { delivery_request_id: 31, reference: "DR-synthetic", business_name: "Dashboard", pickup_area: "Products", delivery_area: "Orders", status: "assigned", assigned_at: "2026-11-06T10:00:00", finished_at: null };
    const driver = { authError: "", page: 1, status: "", profile: section(driverFixtures().profile), summary: section(driverFixtures().summary), list: section({ total: 1, deliveries: [row] }), detail: section({ delivery: row, events: [{ status: "assigned", occurred_at: row.assigned_at }], allowed_next_status: "picked_up" }), busy: false, uncertain: false, message: "" };
    for (const language of ["en", "ta", "si"]) {
      await suite.test(language + ": Owner catalogue drafts and fixed option values survive switching", async () => {
        const before = workflow.getSnapshot(), customerBefore = catalogue.getSnapshot();
        await i18n.changeLanguage(language);
        const html = render(Products, { state: before, actions: workflow });
        for (const key of ["Product Management", "Edit Product", "Unit price (LKR)", "Save {{kind}}"] ) {
          if (!key.includes("{{")) assert.ok(html.includes(tr(key)), key);
        }
        assert.ok(html.includes('value="Dashboard"'));
        assert.ok(html.includes('value="125.25"'));
        assert.ok(html.includes('value="published"') && html.includes('value="available"'));
        assert.equal(workflow.getSnapshot(), before);
        const shop = render(Catalogue, { state: customerBefore, actions: catalogue, mode: "shop", businessId: 1 });
        assert.ok(shop.includes(tr("Published products")) && shop.includes("Local Shop") && shop.includes("Rice"));
        assert.ok(shop.includes('href="/customer/explore/1/products/31"'));
        assert.equal(catalogue.getSnapshot(), customerBefore);
      });
      await suite.test(language + ": credit sale, repayment and credit account form keep authoritative values", async () => {
        await i18n.changeLanguage(language);
        const before = JSON.stringify(owner);
        const sale = render(Sales, { state: owner, actions: {} });
        assert.ok(sale.includes(tr("Record Credit Sale")) && sale.includes(tr("Outstanding Balance")));
        assert.ok(sale.includes("LKR 70.10") && sale.includes("Dashboard") && sale.includes("Products"));
        assert.ok(sale.includes('value="30.10"'));
        const repayment = render(Repayments, { state: owner, actions: {} });
        assert.ok(repayment.includes(tr("Repayment amount (LKR)")) && repayment.includes('value="cash"'));
        const modal = render(ManageCustomer, { businessId: 1, details: owner.details, mode: "credit", onClose: noop, onSaved: noop });
        assert.ok(modal.includes(tr("Payment terms (days)")) && modal.includes('value="active"') && modal.includes('value="suspended"'));
        assert.equal(JSON.stringify(owner), before);
      });
      await suite.test(language + ": Customer checkout, My Shops and order tracking preserve cart and records", async () => {
        await i18n.changeLanguage(language);
        const cart = { cart: { business_id: 2, items: [{ product_id: 1, business_id: 2, name: "Dashboard", quantity: 2 }] }, pending: { request_key: "synthetic", payment_method: "credit" } };
        const before = JSON.stringify(cart);
        const html = renderToStaticMarkup(h(I18nextProvider, { i18n }, h(MemoryRouter, null, h(ShoppingContext.Provider, { value: cart }, h(Cart, { checkout: true })))));
        assert.ok(html.includes(tr("Shopping Cart & Checkout").replaceAll("&", "&amp;")) && html.includes(tr("Credit — requires Shop Owner approval")));
        assert.ok(html.includes("Dashboard") && html.includes('value="2"'));
        assert.match(html, /<input(?=[^>]*value="credit")(?=[^>]*checked)[^>]*>/);
        assert.equal(JSON.stringify(cart), before);
        const shops = render(MyShopsView, { summary: section({ linked_shop_count: 1, total_outstanding_balance: "70.10" }), shops: section({ total: 1, items: [{ business_id: 2, business_name: "Dashboard", credit_account_count: 1, outstanding_balance: "70.10" }] }), page: 1, onPage: noop });
        assert.ok(shops.includes(tr("Total Linked Shops")) && shops.includes("Dashboard") && shops.includes("70.10"));
        const order = { order_id: 7, reference: "ORD-synthetic", business_name: "Dashboard", status: "submitted", payment_method: "credit", payment_status: "pending", total: "250.50", created_at: "2026-11-07T00:00:00", items: [{ product_id: 1, product_name: "Products", quantity: 2, unit_price: "125.25", line_total: "250.50" }], credit_sale_id: null };
        const tracking = render(OrderRecord, { order });
        assert.ok(tracking.includes(tr("Order:")) && tracking.includes("ORD-synthetic") && tracking.includes("Products"));
        assert.ok(tracking.includes("250.50"));
      });
      await suite.test(language + ": Driver progress and Admin confirmations translate without changing identities", async () => {
        await i18n.changeLanguage(language);
        const html = render(Deliveries, { state: driver, actions: {} });
        assert.ok(html.includes(tr("Assigned Deliveries")) && html.includes(tr("Confirm Pickup")));
        assert.ok(html.includes("DR-synthetic") && html.includes("Dashboard") && html.includes("Products"));
        const timeline = render(Timeline, { status: "assigned", events: [{ status: "assigned", occurred_at: row.assigned_at }] });
        assert.ok(timeline.includes(tr("Recorded delivery progress")) && timeline.includes(tr("Upcoming")));
        const state = { submitting: false, dialog: { action: "suspend", name: "Dashboard", text: "Operator-entered note", error: "" } };
        const confirmation = render(Confirmation, { state, kind: "driver", actions: {} });
        assert.ok(confirmation.includes(tr("Reason (required)")) && confirmation.includes(tr("Cancel")));
        assert.ok(confirmation.includes('value="Operator-entered note"') && confirmation.includes("Dashboard"));
      });
    }
    await suite.test("all workflow literal keys and nested fixed label maps have complete resources", async () => {
      for (const file of files) {
        const source = await readFile(new URL("../src/" + file, import.meta.url), "utf8");
        const tree = parse(source, { ecmaVersion: "latest", sourceType: "module", ecmaFeatures: { jsx: true } });
        walk(tree, (node, parent) => {
          if (node.type === "CallExpression" && node.callee.name === "tr") {
            const arg = node.arguments[0], keys = typeof arg?.value === "string" ? [arg.value] : arg?.type === "MemberExpression" && arg.object.type === "ObjectExpression" ? arg.object.properties.map(p => p.value.value) : [];
            for (const key of keys) for (const lang of ["en", "ta", "si"]) assert.ok(Object.hasOwn(resources[lang].application, key), lang + ": " + key);
          }
          if (node.type === "JSXAttribute" && (node.name.name !== "value" || /^[a-z]/.test(parent.name?.name ?? "")) && ["value", "name", "id", "to", "href", "className", "key"].includes(node.name.name)) walk(node.value, child => {
            assert.ok(!(child.type === "CallExpression" && ["tr", "statusLabel"].includes(child.callee.name)), "machine attributes stay untranslated: " + file);
          });
        });
      }
    });
    await suite.test("raw catalogs reject duplicate keys and mismatched interpolation names", async () => {
      for (const file of ["application.en.json", "application.ta.json", "application.si.json", "en.json", "ta.json", "si.json"]) {
        const raw = await readFile(new URL("../src/i18n/locales/" + file, import.meta.url), "utf8");
        const tree = parse("(" + raw + ")", { ecmaVersion: "latest" });
        walk(tree, node => {
          if (node.type !== "ObjectExpression") return;
          const keys = node.properties.map(p => p.key.value ?? p.key.name);
          assert.equal(new Set(keys).size, keys.length, "duplicate JSON keys in " + file);
        });
      }
      const leaves = (value, prefix = "") => Object.entries(value).flatMap(([key, child]) => typeof child === "string" ? [[prefix + key, child]] : leaves(child, prefix + key + "."));
      for (const namespace of ["application", "translation"]) {
        const english = Object.fromEntries(leaves(resources.en[namespace]));
        for (const language of ["ta", "si"]) {
          const translated = Object.fromEntries(leaves(resources[language][namespace]));
          assert.deepEqual(Object.keys(translated).sort(), Object.keys(english).sort());
          for (const [key, value] of Object.entries(english)) {
            const parameters = text => [...text.matchAll(/{{\s*(\w+)\s*}}/g)].map(match => match[1]).sort();
            assert.deepEqual(parameters(translated[key]), parameters(value), language + ": " + key);
            assert.ok(!translated[key].includes("\uFFFD"), key);
          }
        }
      }
      for (const file of files) {
        const source = await readFile(new URL("../src/" + file, import.meta.url), "utf8");
        walk(parse(source, { ecmaVersion: "latest", sourceType: "module", ecmaFeatures: { jsx: true } }), node => {
          if (node.type !== "CallExpression" || node.callee.name !== "tr" || typeof node.arguments[0]?.value !== "string") return;
          const expected = [...node.arguments[0].value.matchAll(/{{\s*(\w+)\s*}}/g)].map(match => match[1]).sort();
          if (!expected.length) return;
          assert.equal(node.arguments[1]?.type, "ObjectExpression");
          assert.deepEqual(node.arguments[1].properties.map(p => p.key.name ?? p.key.value).sort(), expected, file);
        });
      }
    });
    await suite.test("summary placeholders, known failures and copy feedback translate; generated text remains data", async () => {
      const { TamilCreditSummaryView, tamilSummaryError } = await server.ssrLoadModule("/src/components/shopOwner/TamilCreditSummary.jsx");
      const { qrError } = await server.ssrLoadModule("/src/components/shopOwner/ShopQRCode.jsx");
      for (const language of ["en", "ta", "si"]) {
        await i18n.changeLanguage(language);
        const state = { loading: false, data: { summary: "Dashboard 70.10 — synthetic supplied text", source: "fallback", captured_at: "2026-11-15T10:00:00Z", total_credit_purchases: "100.20", total_repayments: "30.10", outstanding_balance: "70.10", overdue_balance: null }, error: "", retryable: false, copyStatus: "Summary copied to the clipboard." };
        const html = render(TamilCreditSummaryView, { state, onGenerate: noop, onCopy: noop });
        assert.ok(html.includes(tr("Not authoritatively available")));
        assert.ok(html.includes(tr("Explain the customer’s credit position simply in Tamil.")));
        assert.ok(html.includes(tr(state.copyStatus)));
        assert.ok(html.includes(state.data.summary) && html.includes("LKR 100.20") && html.includes("LKR 70.10"));
        for (const status of [401, 403, 404, 429, 422, 503]) {
          const message = tamilSummaryError({ response: { status } }).message;
          assert.ok(Object.hasOwn(resources[language].application, message));
          const failed = render(TamilCreditSummaryView, { state: { ...state, data: null, error: message, retryable: true }, onGenerate: noop });
          assert.ok(failed.includes(tr(message)));
        }
        for (const status of [401, 403, 404, 409, 503]) assert.ok(Object.hasOwn(resources[language].application, qrError({ response: { status } })));
        const joined = i18n.t("Join {{business}} on LankaPex", { ns: "application", business: "Dashboard" });
        assert.ok(joined.includes("Dashboard") && !joined.includes("{{"));
      }
    });
    await suite.test("known errors translate while unknown messages retain English fallback", async () => {
      await i18n.changeLanguage("ta");
      assert.notEqual(tr("Repayment amount exceeds outstanding balance."), "Repayment amount exceeds outstanding balance.");
      assert.equal(i18n.t("Unrecognized server condition", { ns: "application", defaultValue: "Unrecognized server condition" }), "Unrecognized server condition");
    });
  } finally { await server.close(); }
});
