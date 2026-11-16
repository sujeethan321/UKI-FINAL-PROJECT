import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { createServer } from "vite";

const code = "A".repeat(32);
const customer = { user_id: 4, platform_role: "customer", account_status: "active" };

test("public QR join view, role and status states, and guarded submission", async () => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { JoinShopView, validPublicCode, previewError, requestError, requestStatus,
      validateJoinStatus, canRequestJoin, statusLookupError,
      submitJoinRequest } = await server.ssrLoadModule("/src/pages/customer/JoinShop.jsx");
    const render = changes => renderToStaticMarkup(createElement(MemoryRouter, null,
      createElement(JoinShopView, {
        codeValid: true, preview: { business_name: "Test Grocery", business_type: "retail" },
        previewLoading: false, previewFailure: "", onRetry() {}, authLoading: false,
        isAuthenticated: false, user: null, notice: "", joinStatus: null, statusLoading: false,
        statusError: "", onRetryStatus() {}, acting: false, actionError: "", onSubmit() {}, onCancel() {},
        requests: null, requestsLoading: false,
        requestsError: "", requestPage: 1, onPage() {}, onRetryRequests() {}, ...changes,
      })));
    assert.equal(validPublicCode(code), true);
    assert.equal(validPublicCode("A".repeat(31)), false);
    assert.equal(validPublicCode("A".repeat(31) + "/"), false);
    assert.equal(validPublicCode("A".repeat(31) + "%"), false);
    const invalid = render({ codeValid: false, preview: null });
    assert.match(invalid, /QR link is invalid/);
    assert.doesNotMatch(invalid, /Test Grocery|Request to Join/);
    const loading = render({ preview: null, previewLoading: true });
    assert.match(loading, /Loading shop/);
    const unavailable = render({ preview: null, previewFailure: previewError({ response: { status: 404 } }) });
    assert.match(unavailable, /shop link is unavailable|Retry/);
    assert.match(previewError({}), /Check your connection/);
    const publicView = render();
    assert.match(publicView, /Test Grocery|retail|Sign In|Register as Customer/);
    assert.match(publicView, /does not create a credit account/);
    assert.doesNotMatch(publicView, /business_id|customer_id|credit_limit|outstanding_balance/);
    const active = render({ isAuthenticated: true, user: customer, joinStatus: { request_id: null, status: "none" } });
    assert.match(active, /Request to Join/);
    assert.doesNotMatch(render({ isAuthenticated: true, user: customer, statusLoading: true }), /<button[^>]*>Request to Join<\/button>/);
    assert.doesNotMatch(render({ isAuthenticated: true, user: { ...customer, platform_role: "driver" } }), /<button[^>]*>Request to Join<\/button>/);
    assert.match(render({ isAuthenticated: true, user: { ...customer, account_status: "suspended" } }), /Only an active Customer/);
    for (const status of ["none", "pending", "approved", "rejected", "cancelled", "already_linked"]) {
      assert.match(requestStatus(status), /request|review|Approved|Rejected|Cancelled|Connected/);
      assert.match(render({ isAuthenticated: true, user: customer, requests: {
        total: 1, requests: [{ request_id: 8, business_name: "Listed Shop", status }],
      } }), /Listed Shop/);
    }
    assert.match(render({ isAuthenticated: true, user: customer, joinStatus: { request_id: 8, status: "pending" } }), /Pending shop-owner review|Cancel request/);
    assert.match(render({ isAuthenticated: true, user: customer, joinStatus: { request_id: null, status: "none" }, acting: true }), /disabled=""[^>]*>Updating request/);
    assert.match(render({ isAuthenticated: true, user: customer, joinStatus: { request_id: 8, status: "pending" }, acting: true }), /disabled=""[^>]*>Cancel request/);
    for (const status of ["none", "pending", "approved", "rejected", "cancelled", "already_linked"]) {
      const request_id = ["none", "already_linked"].includes(status) ? null : 8;
      assert.deepEqual(validateJoinStatus({ request_id, status }), { request_id, status });
      const html = render({ isAuthenticated: true, user: customer, joinStatus: { request_id, status } });
      assert.equal(/<button[^>]*>Request to Join<\/button>/.test(html), canRequestJoin(status));
      assert.equal(/Cancel request/.test(html), status === "pending");
      assert.equal(/href="\/customer\/shops"/.test(html), ["approved", "already_linked"].includes(status));
    }
    for (const bad of [{}, { request_id: 3, status: "none" }, { request_id: null, status: "pending" },
      { request_id: 0, status: "approved" }, { request_id: 5, status: "unknown" }]) {
      assert.throws(() => validateJoinStatus(bad));
    }
    for (const status of [401, 403, 404, 409, 422]) {
      assert.equal(typeof statusLookupError({ response: { status } }), "string");
    }
    assert.match(render({ isAuthenticated: true, user: customer, statusError: statusLookupError({ response: { status: 409 } }) }), /Retry status/);
    assert.match(requestError({ response: { status: 409 } }), /already be linked/);
    assert.match(requestError({ response: { status: 401 } }), /session expired/);
    assert.match(render({ isAuthenticated: true, user: customer, actionError: requestError({ response: { status: 409 } }) }), /Check My Shops/);
    let sent = 0;
    assert.deepEqual(await submitJoinRequest(code, async value => { sent++; assert.equal(value, code); return { status: "pending" }; }), { status: "pending" });
    await assert.rejects(submitJoinRequest("bad", async () => { sent++; }), TypeError);
    await assert.rejects(submitJoinRequest(code, async () => ({ status: "unexpected" })));
    assert.equal(sent, 1);
    const app = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
    assert.match(app, /path="\/join\/:publicCode" element=\{<JoinShop \/>\}/);
    assert.ok(app.indexOf('path="/join/:publicCode"') < app.indexOf("<ProtectedRoute"));
    const source = await readFile(new URL("../src/pages/customer/JoinShop.jsx", import.meta.url), "utf8");
    assert.ok(source.indexOf("if (!codeValid) return;") < source.indexOf("getBusinessJoinPreview(publicCode)"));
    assert.match(source, /getCustomerJoinRequestByCode\(publicCode\)/);
    assert.match(source, /return \(\) => \{ active = false; \};/);
    assert.match(source, /statusState\?\.identityKey === identityKey/);
    assert.match(source, /identityRef\.current === identityKey/);
    assert.match(source, /actionLock\.current/);
    assert.match(source, /cancelCustomerJoinRequest\(currentStatus\.value\.request_id\)/);
    assert.match(source, /setStatusRetry\(value => value \+ 1\)/);
    assert.match(source, /<JoinShopSession key=\{publicCode\}/);
    assert.doesNotMatch(source, /requests\.requests\.find\(|business_name === preview\.business_name/);
    assert.doesNotMatch(source, /customer_link_invitations|business_id|credit_account_id/);
  } finally {
    await server.close();
  }
});
