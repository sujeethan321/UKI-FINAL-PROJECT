import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { createServer } from "vite";
import { parseCustomerPage } from "../src/utils/customerAccounts.js";

const ready = data => ({ data, loading: false, error: "", status: null });
const shop = { business_id: 7, business_name: "Fictional Grocery", credit_account_count: 0, outstanding_balance: "0.00" };
const request = (status = "pending", request_id = 11) => ({ request_id, business_name: "Fictional Grocery", status, created_at: "2026-11-12T10:00:00" });

test("Customer My Shops QR integration", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { MyShopsView } = await server.ssrLoadModule("/src/pages/customer/MyShops.jsx");
    const joins = await server.ssrLoadModule("/src/components/customer/CustomerJoinRequests.jsx");
    const render = props => renderToStaticMarkup(createElement(MemoryRouter, null, createElement(MyShopsView, { summary: ready({ linked_shop_count: 1, total_outstanding_balance: "0.00" }), shops: ready({ total: 1, items: [shop] }), page: 1, onPage() {}, retrySummary() {}, retryShops() {}, ...props })));
    await t.test("approved relationship is a shop card without automatic credit", () => {
      const html = render();
      assert.match(html, /Fictional Grocery/);
      assert.match(html, /Connected shop/);
      assert.match(html, /No credit account at this shop yet/);
      assert.doesNotMatch(html, /View Details/);
      const credit = render({ shops: ready({ total: 1, items: [{ ...shop, credit_account_count: 1 }] }) });
      assert.match(credit, /View Details/);
      assert.match(credit, /Credit purchasing depends on your account status/);
    });
    await t.test("duplicate business rows are rejected before cards are rendered", () => {
      assert.throws(() => parseCustomerPage("shops", { currency: "LKR", page: 1, page_size: 10, total: 2, shops: [shop, shop] }, 1));
    });
    await t.test("pending requests stay separate from approved shop cards", () => {
      const page = joins.parseJoinRequestPage({ page: 1, page_size: 20, total: 2, requests: [request(), request("approved", 12)] }, 1);
      assert.equal(page.requests[0].status, "pending");
      assert.equal(joins.canCancelJoinRequest(page.requests[0]), true);
      assert.equal(joins.canCancelJoinRequest(page.requests[1]), false);
      assert.doesNotMatch(render({ shops: ready({ total: 0, items: [] }) }), /Fictional Grocery/);
      assert.throws(() => joins.parseJoinRequestPage({ page: 1, page_size: 20, total: 2, requests: [request(), request()] }, 1));
    });
    await t.test("only pending requests can cancel and duplicate calls are locked", async () => {
      let resolve, calls = 0;
      const deferred = new Promise(done => { resolve = done; });
      const lock = { current: false };
      const send = async () => { calls++; return deferred; };
      const first = joins.cancelPendingRequest(request(), lock, send);
      assert.equal(await joins.cancelPendingRequest(request(), lock, send), null);
      assert.equal(await joins.cancelPendingRequest(request("approved"), { current: false }, send), null);
      assert.equal(calls, 1);
      resolve({ request_id: 11, status: "cancelled" });
      assert.equal((await first).status, "cancelled");
      assert.equal(lock.current, false);
      await assert.rejects(joins.cancelPendingRequest(request(), lock, async () => ({ request_id: 99, status: "cancelled" })));
    });
    await t.test("errors, pagination and return refresh remain explicit", async () => {
      assert.match(joins.joinRequestMessage({ response: { status: 401 } }), /session expired/);
      assert.match(joins.joinRequestMessage({ response: { status: 409 } }), /already changed/);
      assert.match(joins.joinRequestMessage({}), /connection and retry/);
      const page = await readFile(new URL("../src/pages/customer/MyShops.jsx", import.meta.url), "utf8");
      const section = await readFile(new URL("../src/components/customer/CustomerJoinRequests.jsx", import.meta.url), "utf8");
      assert.match(page, /window\.addEventListener\("focus", refresh\)/);
      assert.match(page, /<CustomerJoinRequests \/>/);
      assert.match(section, /getCustomerJoinRequests\(page, PAGE_SIZE\)/);
      assert.match(section, /page \* PAGE_SIZE >= data\.total/);
      assert.match(section, /Refresh requests/);
      assert.match(section, /No join requests yet/);
    });
  } finally { await server.close(); }
});
