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
    const { default: LandingPage, FaqAccordion } = await server.ssrLoadModule("/src/pages/landing/LandingPage.jsx");
    const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(LandingPage)));
    const section = id => html.split('id="' + id + '"')[1].split('</section>')[0];
    await t.test("original headline, hero tiles and feature overview remain", () => {
      assert.ok(html.includes('Digital Credit<br/>Management<br/>&amp; <span>Delivery Platform'));
      assert.equal((html.match(/class="landing-icon-tile"/g) || []).length, 4);
      assert.equal((section("features").match(/<article/g) || []).length, 4);
      for (const text of ["Digital Credit Management", "Credit Purchases", "Delivery Management", "Reports &amp; Insights", "Replace handwritten Nayam"]) assert.ok(html.includes(text));
    });
    await t.test("new sections follow statistics in requested order", () => {
      const ids = ["how-it-works", "who-can-use", "why-lankapex", "explore-features", "faq", "contact"];
      let last = html.indexOf('class="landing-statistics"');
      for (const id of ids) { const position = html.indexOf('id="' + id + '"'); assert.ok(position > last); last = position; }
      assert.equal((section("how-it-works").match(/<li /g) || []).length, 4);
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
    await t.test("detailed features label planned commerce and manual WhatsApp accurately", () => {
      const details = section("explore-features");
      assert.equal((details.match(/<article/g) || []).length, 6);
      assert.equal((details.match(/class="landing-status">Planned/g) || []).length, 2);
      for (const text of ["Digital Credit Ledger", "Customer Management", "Payment Reminders", "Notifications", "English and Tamil", "does not confirm message delivery", "recorded customer permission"]) assert.ok(details.includes(text));
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
      assert.ok(html.includes('not verified adoption or security metrics'));
    });
  } finally { await server.close(); }
});
