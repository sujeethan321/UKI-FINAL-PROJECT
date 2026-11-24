import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { createServer } from "vite";

test("authentication UI and protected route isolation", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { AuthContext } = await server.ssrLoadModule("/src/context/AuthContext.jsx");
    const { default: ProtectedRoute } = await server.ssrLoadModule("/src/routes/ProtectedRoute.jsx");
    const renderGuard = auth => renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: ["/protected"] }, createElement(AuthContext.Provider, { value: auth }, createElement(Routes, null, createElement(Route, { element: createElement(ProtectedRoute, { allowedRoles: ["shop_owner"] }) }, createElement(Route, { path: "/protected", element: createElement("p", null, "Private owner content") }))))));
    await t.test("loading, logout and wrong role never render private owner content", () => { for (const auth of [{ loading: true }, { loading: false, isAuthenticated: false, user: null }, { loading: false, isAuthenticated: true, user: { account_status: "active", platform_role: "customer" } }, { loading: false, isAuthenticated: true, user: { account_status: "active", platform_role: "driver" } }, { loading: false, isAuthenticated: true, user: { account_status: "active", platform_role: "admin" } }]) assert.ok(!renderGuard(auth).includes("Private owner content")); });
    await t.test("verified allowed role renders its protected content", () => { assert.match(renderGuard({ loading: false, isAuthenticated: true, user: { account_status: "active", platform_role: "shop_owner" } }), /Private owner content/); });
    await t.test("missing, unsupported and inactive identities cannot render a protected dashboard", () => {
      for (const user of [{ platform_role: "shop_owner", account_status: "pending" }, { platform_role: "shop_owner", account_status: "suspended" }, { platform_role: "unknown", account_status: "active" }, { platform_role: "toString", account_status: "active" }, {}]) {
        assert.ok(!renderGuard({ loading: false, isAuthenticated: true, user }).includes("Private owner content"));
      }
    });
    await t.test("every role can render its own dashboard and cross-role deep links remain blocked", () => {
      const roles = ["shop_owner", "customer", "driver", "admin"];
      for (const target of roles) for (const actual of roles) {
        const auth = { loading: false, isAuthenticated: true, user: { user_id: 1, account_status: "active", platform_role: actual } };
        const html = renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: ["/target?returnTo=https://example.com/admin"] }, createElement(AuthContext.Provider, { value: auth }, createElement(Routes, null,
          createElement(Route, { element: createElement(ProtectedRoute, { allowedRoles: [target] }) }, createElement(Route, { path: "/target", element: createElement("p", null, "Protected dashboard " + target) }))))));
        assert.equal(html.includes("Protected dashboard " + target), target === actual);
        assert.ok(!html.includes('href="https://example.com'));
      }
    });
    await t.test("real Login and Registration pages still render without credentials in markup", async () => { for (const [module, url] of [["/src/pages/auth/LoginPage.jsx", "/login"], ["/src/pages/auth/RegisterPage.jsx", "/register/customer"]]) { const { default: Page } = await server.ssrLoadModule(module); const html = renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: [url] }, createElement(AuthContext.Provider, { value: { login: async () => {}, user: null, isAuthenticated: false } }, createElement(Routes, null, createElement(Route, { path: url.includes("login") ? "/login" : "/register/:role", element: createElement(Page) }))))); assert.match(html, /<form/); assert.match(html, /type="password"/); assert.ok(!html.includes("Bearer ")); } });
  } finally { await server.close(); }
});

test("raw Axios errors cannot leak authorization headers through legacy logs", async () => {
  for (const name of ["src/pages/shopOwner/BusinessOnboarding.jsx", "src/components/ApiConnectionTest.jsx"]) {
    const text = await readFile(new URL("../" + name, import.meta.url), "utf8");
    assert.ok(!text.includes("console.error"), name);
  }
});
