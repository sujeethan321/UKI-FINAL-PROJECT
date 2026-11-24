import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter, Routes, Navigate, Outlet, createRoutesFromElements, matchRoutes } from 'react-router-dom';
import { createServer } from 'vite';

test('actual application routes preserve protected roots, fallbacks and deep links', async t => {
  const server = await createServer({ logLevel: 'silent', appType: 'custom', server: { middlewareMode: true, hmr: false } });
  try {
    const { default: App } = await server.ssrLoadModule('/src/App.jsx');
    const { default: Guard } = await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
    const { AuthContext } = await server.ssrLoadModule('/src/context/AuthContext.jsx');
    function findRoutes(node) {
      if (node?.type === Routes) return node;
      for (const child of [node?.props?.children].flat(Infinity)) {
        const found = child && typeof child === 'object' ? findRoutes(child) : null;
        if (found) return found;
      }
      return null;
    }
    const routes = createRoutesFromElements(findRoutes(App()).props.children);
    const roles = { shop_owner: '/shop-owner', customer: '/customer', driver: '/driver', admin: '/admin' };
    const session = role => ({ loading: false, isAuthenticated: Boolean(role),
      user: role ? { platform_role: role, account_status: 'active' } : null });
    function guard(props, auth) {
      let result;
      function Probe() { result = Guard(props); return null; }
      renderToStaticMarkup(h(MemoryRouter, null, h(AuthContext.Provider, { value: auth }, h(Probe))));
      return result;
    }
    // Match the real App route tree and evaluate the real guard. Follow Navigate
    // elements without mounting page effects, issuing requests or starting apps.
    function resolve(initial, auth) {
      let path = initial;
      const visited = [];
      for (let count = 0; count < 5; count++) {
        assert.ok(!visited.includes(path), 'redirect loop: ' + path);
        visited.push(path);
        const matches = matchRoutes(routes, path);
        assert.ok(matches?.length, path);
        let redirect;
        for (const { route } of matches) {
          let element = route.element;
          if (element?.type === Guard) {
            element = guard(element.props, auth);
            if (element.type !== Navigate && element.type !== Outlet) return { path, waiting: true };
          }
          if (element?.type === Navigate) {
            assert.equal(element.props.replace, true);
            redirect = element.props.to;
            break;
          }
        }
        if (!redirect) return { path, leaf: matches.at(-1).route.element.type, visited };
        path = redirect;
      }
      assert.fail('too many redirects');
    }
    await t.test('all four roots and trailing slashes redirect to their protected dashboards', () => {
      for (const [role, root] of Object.entries(roles)) {
        for (const path of [root, root + '/']) {
          const result = resolve(path, session(role));
          assert.equal(result.path, root + '/dashboard');
          assert.equal(result.visited.length, 2);
        }
      }
    });
    await t.test('signed-out, wrong-role and inactive users cannot bypass root or deep-link guards', () => {
      for (const [role, root] of Object.entries(roles)) {
        for (const path of [root, root + '/dashboard']) {
          assert.equal(resolve(path, session(null)).path, '/login');
          const inactive = session(role); inactive.user.account_status = 'suspended';
          assert.equal(resolve(path, inactive).path, '/login');
          for (const [other, otherRoot] of Object.entries(roles)) {
            if (other !== role) assert.equal(resolve(path, session(other)).path, otherRoot + '/dashboard');
          }
        }
        assert.equal(resolve(root, { loading: true }).waiting, true);
      }
    });
    await t.test('unknown URLs reach the public landing page without loops', () => {
      for (const role of [null, ...Object.keys(roles)]) {
        for (const path of ['/unknown-viva-url', '/customer/not-a-page', '/driver/not-a-page']) {
          assert.equal(resolve(path, session(role)).path, '/');
        }
      }
    });
    await t.test('join, login, registration and valid private deep links retain exact destinations', () => {
      for (const path of ['/join/fictional-public-code', '/login', '/register/customer']) {
        for (const role of [null, ...Object.keys(roles)]) assert.equal(resolve(path, session(role)).path, path);
      }
      for (const [role, path] of [
        ['shop_owner', '/shop-owner/reports'], ['shop_owner', '/shop-owner/subscription?business_id=1&checkout=success'],
        ['shop_owner', '/shop-owner/orders/123'], ['customer', '/customer/orders/123'],
        ['customer', '/customer/explore/1/products/2'], ['customer', '/customer/credit/3/statement'],
        ['driver', '/driver/deliveries/123'], ['admin', '/admin/businesses'],
      ]) assert.equal(resolve(path, session(role)).path, path);
      assert.equal(resolve('/shop-owner/credit-orders', session('shop_owner')).path, '/shop-owner/orders');
      assert.equal(resolve('/login/customer', session(null)).path, '/login');
    });
  } finally { await server.close(); }
});
