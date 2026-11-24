import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { createServer } from "vite";

test("public landing page and enhancement contracts", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { default: LandingPage, FaqAccordion, RoleShowcase } = await server.ssrLoadModule("/src/pages/landing/LandingPage.jsx");
    const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(LandingPage)));
    const section = id => html.split('id="' + id + '"')[1].split('</section>')[0];
    await t.test("hero registration actions remain and Features targets the retained Explore section", () => {
      assert.ok(html.includes('Digital Credit<br/>Management<br/>&amp; <span>Delivery Platform'));
      assert.equal((html.match(/class="landing-icon-tile"/g) || []).length, 0);
      const actions = html.split('class="landing-hero-actions"')[1].split('</div>')[0];
      for (const [role, label] of [["shop-owner", "Shop Owner"], ["customer", "Customer"], ["driver", "Delivery Driver"]]) {
        assert.ok(actions.includes('href="/register/' + role + '"'));
        assert.ok(actions.includes('Register as ' + label));
      }
      assert.equal((actions.match(/<a /g) || []).length, 3);
      assert.equal((actions.match(/class="landing-button registration"/g) || []).length, 3);
      assert.ok(!actions.includes('href="/login"'));
      assert.ok(!actions.includes('Learn More'));
      assert.ok(!html.includes('id="features"'));
      assert.ok(html.includes('href="#explore-features"'));
      assert.equal((section("explore-features").match(/<article/g) || []).length, 6);
    });
    await t.test("hero button motion is shared, pointer-gated and reduced-motion aware", async () => {
      const css = await readFile(new URL('../src/pages/landing/landing.css', import.meta.url), 'utf8');
      assert.ok(css.includes('background:rgba(245,248,252,.4)'));
      assert.ok(css.includes('border:1.5px solid #006d80'));
      assert.ok(css.includes('@media(hover:hover) and (pointer:fine)'));
      assert.ok(css.includes('background:#00e8cf'));
      assert.ok(css.includes('transform:translateY(-3px)'));
      assert.ok(css.includes('transform:translateX(7px)'));
      assert.ok(css.includes('box-shadow:0 12px 26px rgba(0,190,170,.22)'));
      assert.ok(css.includes('transition:transform 280ms ease'));
      assert.match(css, /@media\(prefers-reduced-motion:reduce\)\s*\{[^]*?\.registration svg \{ transition:none \}/);
      assert.ok(css.includes('a:focus-visible'));
    });
    await t.test("sections follow the current navbar order", () => {
      const ids = ["explore-features", "how-it-works", "who-can-use", "why-lankapex", "faq", "contact"];
      let last = html.indexOf('class="landing-hero"');
      for (const id of ids) { const position = html.indexOf('id="' + id + '"'); assert.ok(position > last); last = position; }
      assert.equal((section("how-it-works").match(/<li[ >]/g) || []).length, 4);
      assert.equal((section("why-lankapex").match(/<article/g) || []).length, 4);
    });
    await t.test("exactly three public registration roles and truthful dashboard status", () => {
      const roles = section("who-can-use");
      assert.equal((roles.match(/<article/g) || []).length, 3);
      for (const role of ["shop-owner", "customer", "driver"]) assert.ok(roles.includes('href="/register/' + role + '"'));
      assert.ok(!html.includes('/register/admin'));
      assert.ok(roles.includes('customer dashboard currently shows account identity'));
      assert.ok(roles.includes('Delivery workflows are planned'));
    });
    await t.test("role tabs select panels with click, arrows, Home and End", () => {
      let selectedRole = 0;
      const view = () => RoleShowcase({ selectedRole, onSelect: index => { selectedRole = index; } });
      const tabs = () => view().props.children[0].props.children;
      const panelHtml = () => renderToStaticMarkup(createElement(MemoryRouter, null, view()));
      assert.equal((panelHtml().match(/role="tabpanel"/g) || []).length, 3);
      assert.equal((panelHtml().match(/ hidden=""/g) || []).length, 2);
      tabs()[1].props.onClick();
      assert.equal(selectedRole, 1);
      assert.equal(tabs()[1].props['aria-selected'], true);
      assert.equal(tabs()[1].props.tabIndex, 0);
      const focused = [];
      const nodes = [0, 1, 2].map(index => ({ focus: () => focused.push(index) }));
      function key(value) {
        let prevented = false;
        tabs()[selectedRole].props.onKeyDown({ key: value, preventDefault: () => { prevented = true; },
          currentTarget: { parentElement: { querySelectorAll: () => nodes } } });
        return prevented;
      }
      assert.ok(key('End')); assert.equal(selectedRole, 2);
      assert.ok(key('ArrowRight')); assert.equal(selectedRole, 0);
      assert.ok(key('ArrowLeft')); assert.equal(selectedRole, 2);
      assert.ok(key('Home')); assert.equal(selectedRole, 0);
      assert.equal(key('Tab'), false);
      assert.deepEqual(focused, [2, 0, 2, 0]);
    });
    await t.test("detailed features label planned commerce and manual WhatsApp accurately", () => {
      const details = section("explore-features");
      assert.equal((details.match(/<article/g) || []).length, 6);
      assert.equal((details.match(/class="landing-status">Planned/g) || []).length, 2);
      for (const text of ["Digital Credit Ledger", "Customer Management", "Payment Reminders", "Notifications", "English and Tamil", "does not confirm message delivery", "recorded customer permission"]) assert.ok(details.includes(text));
    });
    await t.test("glass card styling is scoped, noninteractive and motion-aware", async () => {
      const details = section("explore-features");
      assert.equal((details.match(/class="landing-info-card"/g) || []).length, 6);
      assert.ok(!details.includes('role="button"'));
      assert.ok(!details.includes('tabindex='));
      const css = await readFile(new URL('../src/pages/landing/landing.css', import.meta.url), 'utf8');
      assert.ok(css.includes('#explore-features .landing-info-card {'));
      assert.ok(css.includes('background:rgba(255,255,255,.88)'));
      assert.ok(css.includes('@supports ((backdrop-filter:blur(16px))'));
      assert.ok(css.includes('transform:translateY(-4px)'));
      assert.ok(css.includes('#explore-features .landing-info-card:hover .landing-icon-circle svg { transform:scale(1.05) }'));
      assert.ok(css.includes('#explore-features .landing-info-card .landing-icon-circle svg { transition:none }'));
    });
    await t.test("existing Explore heading has scoped split styling and exact accessible text", async () => {
      const details = section("explore-features");
      assert.ok(details.includes('<h2 id="explore-heading">Explore LankaPex <span>Features</span></h2>'));
      assert.ok(details.includes('Tools for managing credit today and connecting more business activities in the future.'));
      assert.ok(details.includes('class="landing-explore-line" aria-hidden="true"'));
      const css = await readFile(new URL('../src/pages/landing/landing.css', import.meta.url), 'utf8');
      assert.ok(css.includes('font-size:clamp(29px,3.5vw,47px)'));
      assert.ok(css.includes('width:65px; height:4px; background:#12b8a6'));
      assert.ok(css.includes('.landing-explore-heading h2 span:hover { color:#00e8cf }'));
      assert.ok(css.includes('.landing-explore-heading h2,.landing-explore-subtitle,.landing-explore-line { animation:none }'));
    });
    await t.test("all anchors resolve and account routes exist", async () => {
      const ids = new Set([...html.matchAll(/ id="([^"]+)"/g)].map(m => m[1]));
      assert.equal(ids.size, [...html.matchAll(/ id="([^"]+)"/g)].length);
      for (const match of html.matchAll(/href="#([^"]+)"/g)) assert.ok(ids.has(match[1]), match[1]);
      const app = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8');
      for (const route of ['/login', '/register', '/register/:role']) assert.ok(app.includes('path="' + route + '"'));
      assert.ok(html.includes('href="/login"')); assert.ok(html.includes('href="/register"'));
      assert.ok(!html.includes('content is coming later'));
      assert.ok(html.includes('Contact details coming soon'));
    });
    await t.test("FAQ toggles one panel, closes it, and uses native keyboard buttons", () => {
      let openFaq = null;
      const onToggle = index => { openFaq = openFaq === index ? null : index; };
      const view = () => FaqAccordion({ openFaq, onToggle });
      const render = () => renderToStaticMarkup(view());
      const press = index => view().props.children[index].props.children[0].props.children.props.onClick();
      assert.equal((render().match(/aria-expanded="false"/g) || []).length, 6);
      press(0); assert.equal(openFaq, 0); assert.equal((render().match(/aria-expanded="true"/g) || []).length, 1);
      assert.ok(render().includes('id="faq-answer-0" role="region" aria-labelledby="faq-question-0"><p>'));
      press(1); assert.equal(openFaq, 1); assert.equal((render().match(/aria-expanded="true"/g) || []).length, 1);
      press(1); assert.equal(openFaq, null);
      const button = view().props.children[0].props.children[0].props.children;
      assert.equal(button.type, 'button'); assert.equal(button.props.type, 'button');
      assert.equal(button.props['aria-controls'], 'faq-answer-0');
    });
    await t.test("assets, existing colors, responsive grids, focus and reduced motion remain", async () => {
      for (const file of ["landing-hero.png", "lankapex-logo.png"]) assert.ok((await stat(new URL('../src/assets/' + file, import.meta.url))).size > 1000);
      assert.ok(html.includes('alt="Sri Lankan shop owner')); assert.ok(html.includes('alt="LankaPex'));
      const css = await readFile(new URL('../src/pages/landing/landing.css', import.meta.url), 'utf8');
      assert.ok(css.includes('--navy:#10243e')); assert.ok(css.includes('--teal:#00bfa8'));
      assert.ok(css.includes('prefers-reduced-motion:reduce')); assert.ok(css.includes('focus-visible'));
      assert.ok(css.includes('grid-template-columns:minmax(0,1fr)'));
      assert.ok(!html.includes('landing-statistics'));
      assert.ok(!html.includes('Illustrative platform figures'));
      for (const value of ['500+', '5,000+', '300+', '99%']) assert.ok(!html.includes(value));
    });
  } finally { await server.close(); }
});
