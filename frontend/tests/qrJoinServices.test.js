import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

async function loadService(name, calls) {
  const source = await readFile(new URL(`../src/services/${name}.js`, import.meta.url), "utf8");
  assert.match(source, /^import api from ["']\.\/api["'];/m);
  assert.doesNotMatch(source, /axios\.create|fetch\(|sessionStorage|localStorage|console\./);
  const api = {
    get: async (...args) => { calls.push(["get", ...args]); return { data: { ok: true } }; },
    post: async (...args) => { calls.push(["post", ...args]); return { data: { ok: true } }; },
  };
  const transformed = source.replace(/^import api from ["']\.\/api["'];/m,
    `const api = globalThis.__qrServiceTestApi;`);
  globalThis.__qrServiceTestApi = api;
  try {
    return await import(`data:text/javascript,${encodeURIComponent(transformed)}#${name}`);
  } finally {
    delete globalThis.__qrServiceTestApi;
  }
}

test("customer QR service uses exact API contracts and encodes path segments", async () => {
  const calls = [];
  const service = await loadService("customerJoinService", calls);
  const code = "A".repeat(32);
  await service.getCustomerJoinRequestByCode(code);
  await assert.rejects(service.getCustomerJoinRequestByCode("invalid"), TypeError);
  assert.deepEqual(await service.getBusinessJoinPreview("ab/c?d"), { ok: true });
  await service.requestToJoinShop("opaque-code");
  await service.getCustomerJoinRequests(2, 15);
  await service.cancelCustomerJoinRequest("2/3");
  assert.deepEqual(calls, [
    ["get", `/customer/join-requests/by-code/${code}`],
    ["get", "/business-join/ab%2Fc%3Fd"],
    ["post", "/customer/join-requests", { public_code: "opaque-code" }],
    ["get", "/customer/join-requests", { params: { page: 2, page_size: 15 } }],
    ["post", "/customer/join-requests/2%2F3/cancel"],
  ]);
});

test("owner QR service scopes routes and rejects unsupported decisions before HTTP", async () => {
  const calls = [];
  const service = await loadService("shopOwnerJoinService", calls);
  await service.getOrCreateBusinessJoinLink("1/2");
  await service.getBusinessJoinRequests(7, "pending", 3, 10);
  await service.getBusinessJoinRequests(7);
  await service.decideBusinessJoinRequest(7, "4/5", "approve");
  await service.decideBusinessJoinRequest(7, 5, "reject");
  const before = calls.length;
  await assert.rejects(service.decideBusinessJoinRequest(7, 5, "cancel"), TypeError);
  assert.equal(calls.length, before);
  assert.deepEqual(calls, [
    ["post", "/shop-owner/businesses/1%2F2/join-link"],
    ["get", "/shop-owner/businesses/7/join-requests", { params: { status: "pending", page: 3, page_size: 10 } }],
    ["get", "/shop-owner/businesses/7/join-requests", { params: { page: 1, page_size: 20 } }],
    ["post", "/shop-owner/businesses/7/join-requests/4%2F5/decision", { decision: "approve" }],
    ["post", "/shop-owner/businesses/7/join-requests/5/decision", { decision: "reject" }],
  ]);
});
