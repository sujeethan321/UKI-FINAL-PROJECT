import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const response = {
  summary: "சரிபார்க்கப்பட்ட கடன் சுருக்கம்.", source: "generated",
  provider_status: "available", failure_category: null, currency: "LKR",
  total_credit_purchases: "1000.00", total_repayments: "250.00",
  outstanding_balance: "750.00", overdue_balance: null,
  captured_at: "2026-11-14T12:00:00Z",
};

test('Customer summary section stays visible without an active account or during plan loading',async()=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try {
    const {default:Summary}=await server.ssrLoadModule('/src/components/shopOwner/TamilCreditSummary.jsx');
    const missing=renderToStaticMarkup(createElement(Summary,{businessId:11,customerId:22,creditAccountId:null}));
    assert.ok(missing.includes('Tamil Credit Summary'));
    assert.ok(missing.includes('active credit account'));
    const loading=renderToStaticMarkup(createElement(Summary,{businessId:11,customerId:22,creditAccountId:33}));
    assert.ok(loading.includes('Tamil Credit Summary'));assert.ok(loading.includes('Loading subscription'));
  } finally {await server.close();}
});

test("Shop Owner Tamil credit summary interface", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const service = await server.ssrLoadModule("/src/services/shopOwnerAiSummaryService.js");
    const component = await server.ssrLoadModule("/src/components/shopOwner/TamilCreditSummary.jsx");
    const { default: api } = await server.ssrLoadModule("/src/services/api.js");

    await t.test("service sends exact authenticated POST with no request body", async () => {
      const previousStorage = globalThis.localStorage;
      const originalAdapter = api.defaults.adapter;
      globalThis.localStorage = { getItem: () => "controlled-token" };
      let observed;
      api.defaults.adapter = async config => {
        observed = config;
        return { data: response, status: 200, statusText: "OK", headers: {}, config };
      };
      try {
        assert.deepEqual(await service.generateTamilCreditSummary(11, 22, 33), response);
        assert.equal(observed.method, "post");
        assert.equal(observed.url, "/shop-owner/businesses/11/customers/22/credit-accounts/33/tamil-credit-summary");
        assert.equal(observed.data, undefined);
        assert.equal(observed.headers.get("Authorization"), "Bearer controlled-token");
      } finally {
        api.defaults.adapter = originalAdapter;
        if (previousStorage === undefined) delete globalThis.localStorage;
        else globalThis.localStorage = previousStorage;
      }
    });

    await t.test("invalid identifiers stop before Axios", async () => {
      for (const ids of [[0, 2, 3], [1, "2?x=1", 3], [1, 2, -3], [1, 2, Number.MAX_SAFE_INTEGER + 1]]) {
        await assert.rejects(() => service.generateTamilCreditSummary(...ids), TypeError);
      }
    });

    await t.test("response contract rejects malformed data", () => {
      assert.equal(component.validateTamilSummaryResponse(response).summary, response.summary);
      for (const changed of [{ currency: "USD" }, { outstanding_balance: 750 }, { source: "unknown" },
        { summary: "" }, { captured_at: "not-a-date" }, { failure_category: "private_error" }]) {
        assert.throws(() => component.validateTamilSummaryResponse({ ...response, ...changed }));
      }
    });

    await t.test("safe status messages never expose backend details", () => {
      const secret = "PRIVATE provider body";
      const cases = [[401, /session expired/, false], [403, /permission/, false],
        [404, /unavailable/, false], [429, /limit/, true], [500, /temporarily unavailable/, true]];
      for (const [status, pattern, retry] of cases) {
        const result = component.tamilSummaryError({ response: { status, data: { detail: secret } } });
        assert.match(result.message, pattern); assert.equal(result.retry, retry);
        assert.ok(!result.message.includes(secret));
      }
    });

    await t.test("view separates authoritative facts from Tamil text", () => {
      const html = renderToStaticMarkup(createElement(component.TamilCreditSummaryView, {
        state: { loading: false, data: response, error: "", retryable: false, copyStatus: "" },
        onGenerate() {}, onCopy() {},
      }));
      for (const text of ["Tamil Credit Summary", "AI-assisted verified explanation", "Credit purchases",
        "LKR 1000.00", "LKR 250.00", "LKR 750.00", "Not authoritatively available",
        "Copy summary", "சரிபார்க்கப்பட்ட கடன் சுருக்கம்"]) assert.ok(html.includes(text), text);
      assert.match(html, /lang="ta"/);
      assert.match(html, /does not approve credit or change balances/);
    });

    await t.test("loading, fallback, and retry states are accessible", () => {
      const render = state => renderToStaticMarkup(createElement(component.TamilCreditSummaryView, { state, onGenerate() {}, onCopy() {} }));
      assert.match(render({ loading: true, data: null, error: "", retryable: false, copyStatus: "" }), /Generating/);
      assert.match(render({ loading: false, data: { ...response, source: "fallback", provider_status: "unavailable", failure_category: "configuration" }, error: "", retryable: false, copyStatus: "" }), /Deterministic fallback/);
      const failed = render({ loading: false, data: null, error: "Temporarily unavailable", retryable: true, copyStatus: "" });
      assert.match(failed, /role="alert"/); assert.match(failed, /Retry summary/);
    });

    await t.test("customer screen uses exact context and keyed privacy reset", async () => {
      const page = await readFile(new URL("../src/pages/shopOwner/ShopOwnerCustomers.jsx", import.meta.url), "utf8");
      assert.match(page, /customerDetails\?\.credit_account\?\.account_status === "active"/);
      assert.match(page, /key=\{`\$\{selectedBusinessId\}:\$\{selected\.id\}:\$\{customerDetails\?\.credit_account\?\.credit_account_id \|\| 'none'\}`\}/);
      assert.match(page, /businessId=\{selectedBusinessId\}/);
      assert.match(page, /customerId=\{selected\.id\}/);
      assert.match(page, /creditAccountId=\{customerDetails\?\.credit_account\?\.account_status === "active" \? customerDetails\.credit_account\.credit_account_id : null\}/);
      assert.doesNotMatch(page, /localStorage.*TamilCreditSummary|sessionStorage.*TamilCreditSummary/);
    });
  } finally {
    await server.close();
  }
});
