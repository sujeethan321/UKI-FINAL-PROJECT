import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QRCodeSVG } from "qrcode.react";

const code = "A".repeat(32);

test("owner QR and pending-request guards", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const qr = await server.ssrLoadModule("/src/components/shopOwner/ShopQRCode.jsx");
    const requests = await server.ssrLoadModule("/src/components/shopOwner/PendingCustomerRequests.jsx");
    await t.test("only valid opaque codes make same-origin join links", () => {
      assert.equal(qr.joinUrlForCode("https://lankapex.example", code), `https://lankapex.example/join/${code}`);
      const svg = renderToStaticMarkup(createElement(QRCodeSVG, { value: qr.joinUrlForCode("https://lankapex.example", code), marginSize: 4 }));
      assert.match(svg, /^<svg /);
      assert.match(svg, /<path /);
      for (const value of ["short", `${code}?x=1`, `${code}/extra`, `%41`.repeat(32)]) assert.equal(qr.joinUrlForCode("https://lankapex.example", value), null);
      assert.equal(qr.joinUrlForCode("https://lankapex.example/path", code), null);
      assert.equal(qr.joinUrlForCode("javascript:alert(1)", code), null);
    });
    await t.test("pending page requires valid pending rows", () => {
      const data = { total: 1, page: 1, page_size: 10, requests: [{ request_id: 1, status: "pending" }] };
      assert.equal(requests.pendingResponse(data, 1), data);
      assert.throws(() => requests.pendingResponse({ ...data, page: 2 }, 1));
      assert.throws(() => requests.pendingResponse({ ...data, requests: [{ request_id: 1, status: "approved" }] }, 1));
      assert.throws(() => requests.pendingResponse({ ...data, requests: [{ request_id: 0, status: "pending" }] }, 1));
    });
    await t.test("authorization, conflict and network errors are distinct", () => {
      assert.match(qr.qrError({ response: { status: 403 } }), /approved business owner/);
      assert.match(requests.joinRequestError({ response: { status: 401 } }), /session expired/);
      assert.match(requests.joinRequestError({ response: { status: 403 } }), /cannot manage/);
      assert.match(requests.joinRequestError({ response: { status: 404 } }), /unavailable/);
      assert.match(requests.joinRequestError({ response: { status: 409 } }), /already changed/);
    });
    await t.test("business switch remounts private panels and decisions are locked", async () => {
      const page = await readFile(new URL("../src/pages/shopOwner/ShopOwnerCustomers.jsx", import.meta.url), "utf8");
      const panel = await readFile(new URL("../src/components/shopOwner/PendingCustomerRequests.jsx", import.meta.url), "utf8");
      assert.match(page, /selectedBusiness && isApproved && <>/);
      assert.match(page, /key=\{`qr-\$\{selectedBusinessId\}`\}/);
      assert.match(page, /key=\{`requests-\$\{selectedBusinessId\}`\}/);
      assert.match(page, /onChanged=\{\(\) => setDataReload\(n => n \+ 1\)\}/);
      assert.match(panel, /actionLock\.current \|\| processing/);
      assert.match(panel, /window\.confirm/);
      assert.match(panel, /if \(!activeRef\.current\) return/);
    });
  } finally { await server.close(); }
});
