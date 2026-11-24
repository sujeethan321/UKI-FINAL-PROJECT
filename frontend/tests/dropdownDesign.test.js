import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { createServer } from 'vite';
import { bindFloatingPanel, nextMenuIndex, positionPanel } from '../src/utils/floatingPanel.js';

test('all 48 original selects retain their exact option attributes and control handlers', async () => {
  const inventory = JSON.parse(await readFile(new URL('../docs/dropdown-audit.json', import.meta.url), 'utf8'));
  assert.equal(inventory.reduce((sum, file) => sum + file.controls, 0), 48);
  for (const file of inventory) {
    const text = (await readFile(new URL('../../' + file.file, import.meta.url), 'utf8')).replaceAll('\r\n', '\n');
    assert.deepEqual(text.match(/<option\b[^>]*>/g), file.originalOptions, file.file);
    assert.deepEqual((text.match(/<Select\b[^>]*/g) || []).map(tag => tag.replace('<Select', '<select')),
      file.originalHandlers, file.file);
    assert.doesNotMatch(text, /<select\b/);
  }
});

test('floating panels flip, clamp and fit narrow/short viewports', () => {
  const lower = { left: 900, right: 1000, top: 700, bottom: 744 };
  const position = positionPanel(lower, { width: 384, height: 500 }, { width: 1024, height: 768 });
  assert.equal(position.placement, 'top');
  assert.ok(position.left >= 12 && position.left + position.width <= 1012);
  assert.ok(position.top >= 12 && position.top + Math.min(position.maxHeight, 500) <= lower.top);
  const small = positionPanel({ left: 8, right: 52, top: 20, bottom: 64 },
    { width: 384, height: 700 }, { width: 320, height: 240 });
  assert.equal(small.width, 296);
  assert.ok(small.left >= 12 && small.left + small.width <= 308);
  assert.ok(small.maxHeight <= 240 - 64 - 20);
});

test('menu keyboard movement wraps and handles missing focus/empty menus', () => {
  assert.equal(nextMenuIndex(0, 'ArrowUp', 3), 2);
  assert.equal(nextMenuIndex(2, 'ArrowDown', 3), 0);
  assert.equal(nextMenuIndex(-1, 'ArrowUp', 3), 2);
  assert.equal(nextMenuIndex(1, 'Home', 3), 0);
  assert.equal(nextMenuIndex(0, 'End', 3), 2);
  assert.equal(nextMenuIndex(0, 'ArrowDown', 0), -1);
});

function floatingFixture() {
  const listeners = new Map(), panelListeners = new Map(), windowListeners = new Map();
  let closed = 0;
  const win = { innerWidth: 800, innerHeight: 600,
    addEventListener: (type, fn) => windowListeners.set(type, fn),
    removeEventListener: type => windowListeners.delete(type) };
  const doc = { defaultView: win, activeElement: null,
    addEventListener: (type, fn) => listeners.set(type, fn),
    removeEventListener: type => listeners.delete(type) };
  const trigger = { contains: value => value === trigger,
    getBoundingClientRect: () => ({ left: 700, right: 744, top: 30, bottom: 74 }),
    focus: () => { doc.activeElement = trigger; } };
  const items = ['Profile', 'Settings', 'Log out'].map(textContent => ({ textContent,
    closest: () => null, focus() { doc.activeElement = this; } }));
  const panel = { ownerDocument: doc, offsetWidth: 260, scrollHeight: 200, style: {}, dataset: {},
    querySelectorAll: () => items, contains: value => value === panel || items.includes(value),
    addEventListener: (type, fn) => panelListeners.set(type, fn),
    removeEventListener: type => panelListeners.delete(type), focus: () => { doc.activeElement = panel; } };
  return { doc, trigger, panel, items, listeners, panelListeners, windowListeners,
    close: () => { closed++; }, get closed() { return closed; } };
}

test('outside/Escape dismissal, keyboard navigation, typeahead and event cleanup', () => {
  const fixture = floatingFixture();
  const cleanup = bindFloatingPanel({ ...fixture, menu: true });
  assert.equal(fixture.doc.activeElement, fixture.items[0]);
  const key = key => fixture.listeners.get('keydown')({ key, preventDefault() {}, stopPropagation() {} });
  key('ArrowDown'); assert.equal(fixture.doc.activeElement, fixture.items[1]);
  key('End'); assert.equal(fixture.doc.activeElement, fixture.items[2]);
  key('p'); assert.equal(fixture.doc.activeElement, fixture.items[0]);
  fixture.listeners.get('pointerdown')({ target: fixture.panel }); assert.equal(fixture.closed, 0);
  fixture.listeners.get('pointerdown')({ target: fixture.trigger }); assert.equal(fixture.closed, 0);
  fixture.listeners.get('pointerdown')({ target: {} }); assert.equal(fixture.closed, 1);
  key('Escape'); assert.equal(fixture.closed, 2); assert.equal(fixture.doc.activeElement, fixture.trigger);
  cleanup();
  assert.equal(fixture.listeners.size, 0); assert.equal(fixture.panelListeners.size, 0);
  assert.equal(fixture.windowListeners.size, 0);
});

test('menu Tab continues through the page, Space activates links and scrolling repositions', () => {
  const fixture = floatingFixture();
  const next = { getClientRects: () => [1], closest: () => null, focus() { fixture.doc.activeElement = this; } };
  fixture.trigger.getClientRects = () => [1]; fixture.trigger.closest = () => null;
  fixture.doc.querySelectorAll = () => [fixture.trigger, next];
  let activated = false;
  fixture.items[0].tagName = 'A'; fixture.items[0].click = () => { activated = true; };
  const cleanup = bindFloatingPanel({ ...fixture, menu: true });
  const keyboard = fixture.listeners.get('keydown');
  keyboard({ key: ' ', preventDefault() {} }); assert.equal(activated, true);
  keyboard({ key: 'Tab', preventDefault() {} });
  assert.equal(fixture.doc.activeElement, next); assert.equal(fixture.closed, 1);
  fixture.trigger.getBoundingClientRect = () => ({ left: 700, right: 744, top: 550, bottom: 594 });
  fixture.windowListeners.get('scroll')(); assert.equal(fixture.panel.dataset.placement, 'top');
  cleanup();
});

test('shared components retain native forms, disabled options, multilingual content and semantics', async t => {
  const server = await createServer({ logLevel: 'silent', appType: 'custom', server: { middlewareMode: true, hmr: false } });
  try {
    const { default: Select } = await server.ssrLoadModule('/src/components/ui/Select.jsx');
    await t.test('native select submits original value and retains label/validation/disabled state', () => {
      const html = renderToStaticMarkup(h('label', { htmlFor: 'business' }, 'Business', h(Select, {
        id: 'business', name: 'business_id', required: true, value: '27', disabled: true,
        'aria-invalid': true, 'aria-describedby': 'business-error', onChange() {},
      }, h('option', { value: '' }, 'Choose'), h('option', { value: '27' }, 'தமிழ்'),
      h('option', { value: '28', disabled: true }, 'සිංහල'))));
      for (const value of ['<select', 'lp-select', 'name="business_id"', 'aria-describedby="business-error"',
        'required=""', 'disabled=""', 'value="27" selected=""', 'தமிழ்', 'සිංහල']) assert.ok(html.includes(value), value);
    });
    await t.test('action menu trigger exposes expanded state and popup semantics', async () => {
      const { default: Dropdown } = await server.ssrLoadModule('/src/components/ui/Dropdown.jsx');
      const html = renderToStaticMarkup(h(Dropdown, { label: 'More actions', disabled: true }, h('button', null, 'Archive')));
      assert.match(html, /aria-haspopup="menu"/); assert.match(html, /aria-expanded="false"/);
      assert.match(html, /disabled=""/); assert.doesNotMatch(html, /role="menu"/);
    });
    await t.test('account captions keep role and name with no unsupported action destinations', async () => {
      const { default: AccountMenu } = await server.ssrLoadModule('/src/components/ui/AccountMenu.jsx');
      const html = renderToStaticMarkup(h(MemoryRouter, null, h(AccountMenu, {
        user: { full_name: 'Synthetic Owner' }, roleLabel: 'Shop Owner', onLogout() {},
      })));
      assert.match(html, /Synthetic Owner/); assert.match(html, /Shop Owner/);
      assert.match(html, /lp-avatar/); assert.doesNotMatch(html, /href=/);
    });
    await t.test('open notification panel preserves read/navigation and loading states', async () => {
      const { NotificationBellView } = await server.ssrLoadModule('/src/components/notifications/NotificationBell.jsx');
      const html = renderToStaticMarkup(h(MemoryRouter, null, h(NotificationBellView, {
        state: { open: true, count: 0, recent: { notifications: [] } }, actions: {}, role: 'customer',
      })));
      assert.match(html, /role="dialog"/); assert.match(html, /lp-notification-panel/);
      assert.match(html, /No notifications yet/); assert.match(html, /href="\/customer\/notifications"/);
    });
  } finally { await server.close(); }
});
