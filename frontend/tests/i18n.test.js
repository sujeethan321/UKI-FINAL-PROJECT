import { test } from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { createServer } from "vite";
import { readFile } from "node:fs/promises";

test("public multilingual foundation", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { createAppI18n, readLanguage, bindLanguagePreference, LANGUAGE_STORAGE_KEY, resources } = await server.ssrLoadModule("/src/i18n/index.js");
    const { default: LandingPage } = await server.ssrLoadModule("/src/pages/landing/LandingPage.jsx");
    const instance = createAppI18n();
    const render = () => renderToStaticMarkup(createElement(I18nextProvider, { i18n: instance }, createElement(MemoryRouter, null, createElement(LandingPage))));
    await t.test("English is default; unsupported and unavailable storage fall back safely", () => {
      assert.equal(instance.language, "en");
      assert.equal(readLanguage(), "en");
      assert.equal(readLanguage({ getItem: () => "unknown" }), "en");
      assert.equal(readLanguage({ getItem: () => { throw Error(); } }), "en");
      assert.equal(createAppI18n({ language: "invalid" }).language, "en");
    });
    await t.test("resources have identical keys, array lengths and valid Unicode", () => {
      function leaves(value, prefix = "") {
        if (typeof value === "string") return [prefix];
        return Object.entries(value).flatMap(([key, child]) => leaves(child, `${prefix}.${key}`));
      }
      for (const language of ["ta", "si"]) {
        assert.deepEqual(leaves(resources[language]), leaves(resources.en));
        const text = JSON.stringify(resources[language]);
        assert.ok(!text.includes("\uFFFD"));
        assert.ok(!text.includes("??"));
        assert.ok(language === "ta" ? /[\u0B80-\u0BFF]/.test(text) : /[\u0D80-\u0DFF]/.test(text));
      }
    });
    for (const language of ["en", "ta", "si"]) {
      await t.test(`${language} renders all landing content with unchanged anchors/routes`, async () => {
        await instance.changeLanguage(language);
        const html = render();
        assert.ok(html.includes(`lang="${language}"`));
        assert.ok(html.includes(instance.t("hero.eyebrow")));
        assert.ok(html.includes(instance.t("sections.why.title")));
        assert.ok(html.includes(instance.t("sections.faq.title")));
        assert.ok(html.includes(instance.t("footer.contactDetails")));
        for (const route of ["shop-owner", "customer", "driver"]) assert.ok(html.includes(`href="/register/${route}"`));
        for (const id of ["explore-features", "who-can-use", "how-it-works", "why-lankapex"]) {
          assert.ok(html.includes(`id="${id}"`));
          assert.ok(html.includes(`href="#${id}"`));
        }
        assert.equal((html.match(/class="landing-info-card"/g) || []).length, 6);
        assert.ok(!html.includes("landing-statistics"));
        assert.ok(html.includes('value="en"'));
        assert.ok(html.includes('value="ta"'));
        assert.ok(html.includes('value="si"'));
        assert.ok(html.includes("தமிழ்") && html.includes("සිංහල"));
      });
    }
    await t.test("selection persists across instances and sets document lang without auth storage", async () => {
      const data = new Map();
      const storage = { getItem: key => data.get(key), setItem: (key, value) => data.set(key, value) };
      const document = { documentElement: {} };
      const unbind = bindLanguagePreference(instance, storage, document);
      for (const language of ["ta", "si", "en"]) {
        await instance.changeLanguage(language);
        assert.equal(document.documentElement.lang, language);
        assert.equal(data.get(LANGUAGE_STORAGE_KEY), language);
        assert.equal(createAppI18n({ language: readLanguage(storage) }).language, language);
      }
      assert.deepEqual([...data.keys()], ["lankapex_ui_language"]);
      unbind();
    });
    await t.test("missing Tamil/Sinhala keys use English and blocked persistence is safe", async () => {
      const unbind = bindLanguagePreference(instance, { setItem: () => { throw Error(); } }, { documentElement: {} });
      instance.addResource("en", "translation", "testOnlyFallback", "Safe English fallback");
      for (const language of ["ta", "si"]) {
        await instance.changeLanguage(language);
        assert.equal(instance.t("testOnlyFallback"), "Safe English fallback");
      }
      unbind();
    });
    await t.test("local-script layout permits wrapping without changing registration styling", async () => {
      const css = await readFile(new URL("../src/pages/landing/landing.css", import.meta.url), "utf8");
      assert.ok(css.includes('Inter,"Nirmala UI",Latha,"Iskoola Pota",Arial,sans-serif'));
      assert.match(css, /:lang\(si\) \.landing-hero h1 span \{ white-space:normal \}/);
      assert.match(css, /:lang\(si\) \.landing-role-tabs button \{ overflow-wrap:anywhere \}/);
      assert.ok(css.includes("background:#00e8cf"));
      assert.ok(css.includes("@media(max-width:600px)"));
      const selector = await readFile(new URL("../src/components/LanguageSelector.css", import.meta.url), "utf8") + await readFile(new URL("../src/components/ui/dropdown.css", import.meta.url), "utf8");
      assert.ok(selector.includes("min-height:44px"));
      assert.ok(selector.includes("select:focus-visible"));
    });
  } finally { await server.close(); }
});
