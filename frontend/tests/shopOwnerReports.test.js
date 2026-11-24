import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { createServer } from 'vite';
import { I18nextProvider } from 'react-i18next';

test('wall-clock reports retain the existing sections and real net ledger values', async t => {
  const server = await createServer({ logLevel: 'silent', appType: 'custom', server: { middlewareMode: true, hmr: false } });
  try {
    const { default: Page, ShopOwnerReportsView: View } = await server.ssrLoadModule('/src/pages/shopOwner/ShopOwnerReports.jsx');
    const { createAppI18n } = await server.ssrLoadModule('/src/i18n/index.js');
    const report = { business_id: 1, start_date: '2026-11-01', end_date: '2026-11-02', database_today: '2026-11-02',
      summary: { total_outstanding: '70.05', collected_today: '-30.00', overdue_amount: null },
      totals: { credit_sales: '100.10', repayments: '0.00' },
      daily: [{ date: '2026-11-01', credit_sales: '100.10', repayments: '30.00' },
        { date: '2026-11-02', credit_sales: '0.00', repayments: '-30.00' }] };
    const props = { businesses: [{ business_id: 1, business_name: 'Synthetic', approval_status: 'approved' }], businessId: 1, report };
    const wrap = (node, language = 'en') => h(I18nextProvider, { i18n: createAppI18n({ language }) }, h(MemoryRouter, null, node));
    const render = (extra = {}) => renderToStaticMarkup(wrap(h(View, { ...props, ...extra })));
    await t.test('renders exact totals, negative reversal bars, dates and bounded controls', () => {
      const html = render();
      for (const text of ['Credit Sales Trend', 'Repayment Trend', '100.10', '70.05', '-30', '2026-11-01', 'Maximum 366 days', 'stored database wall clock']) assert.ok(html.includes(text), text);
      assert.equal((html.match(/role="img"/g) || []).length, 2);
      assert.match(html, /fill="#DC4545"/);
      assert.match(html, /name="start_date"/); assert.match(html, /name="end_date"/);
      assert.match(html, /disabled=""[^>]*><svg[^]*?Export Report/);
      assert.ok(html.includes('Aging unavailable'));
    });
    await t.test('loading and errors hide previous private values; empty periods stay zero', () => {
      for (const extra of [{ loading: true }, { error: 'Financial report is unavailable. Check the dates and retry.' }]) {
        const html = render(extra);
        assert.ok(!html.includes('100.10')); assert.ok(!html.includes('70.05'));
        assert.ok(!html.includes('role="img"'));
      }
      const html = render({ report: { ...report, daily: report.daily.map(day => ({ ...day, credit_sales: '0.00', repayments: '0.00' })), totals: { credit_sales: '0.00', repayments: '0.00' } } });
      assert.ok(html.includes('No net activity in this period.'));
      assert.doesNotThrow(() => renderToStaticMarkup(wrap(h(Page))));
    });
    await t.test('form submits only selected wall-clock calendar dates', () => {
      const calls = [];
      const Original = globalThis.FormData;
      globalThis.FormData = class { get(key) { return { start_date: '2026-10-01', end_date: '2026-10-31' }[key]; } };
      function Capture() {
        const tree = View({ ...props, onPeriod: range => calls.push(range) });
        function visit(node) {
          if (!node || typeof node !== 'object') return;
          if (node.type === 'form') node.props.onSubmit({ preventDefault() {}, currentTarget: {} });
          for (const child of [node.props?.children].flat(Infinity)) visit(child);
        }
        visit(tree); return tree;
      }
      try { renderToStaticMarkup(wrap(h(Capture))); } finally { globalThis.FormData = Original; }
      assert.deepEqual(calls, [{ start_date: '2026-10-01', end_date: '2026-10-31' }]);
    });
    await t.test('read-only API contract and business/date stale-response guards remain explicit', async () => {
      const service = await readFile(new URL('../src/services/shopOwnerReportsService.js', import.meta.url), 'utf8');
      assert.match(service, /api\.get\('\/shop-owner\/reports\/financial'/);
      assert.match(service, /business_id: businessId/); assert.match(service, /signal/);
      assert.doesNotMatch(service, /api\.(post|put|patch|delete)/);
      const page = await readFile(new URL('../src/pages/shopOwner/ShopOwnerReports.jsx', import.meta.url), 'utf8');
      assert.match(page, /result\.businessId === businessId/); assert.match(page, /result\.range === range/);
      assert.match(page, /controller\.abort\(\)/);
    });
    await t.test('Reports labels render in Tamil and Sinhala without replacement characters', () => {
      for (const language of ['ta', 'si']) {
        const html = renderToStaticMarkup(wrap(h(View, props), language));
        assert.ok(!html.includes('Business Reports'));
        assert.ok(!html.includes('\uFFFD'));
        assert.ok(!html.includes('????'));
        const i18n = createAppI18n({ language });
        assert.notEqual(i18n.t('Export PDF', { ns: 'application' }), 'Export PDF');
        assert.notEqual(i18n.t('Export CSV', { ns: 'application' }), 'Export CSV');
      }
    });
    await t.test('aging buckets, incomplete coverage and private loading states', () => {
      const aging = { status: 'complete', reconciliation: 'matched', unclassified: '0.00', buckets: {
        current: '12.34', days_1_30: '21.43', days_31_60: '31.54', days_61_90: '41.65', days_91_plus: '51.76' } };
      const html = render({ report: { ...report, aging } });
      for (const text of ['12.34','21.43','31.54','41.65','51.76','91+ days overdue','Reporting-only FIFO','Complete coverage']) assert.ok(html.includes(text), text);
      assert.ok(render({ report: { ...report, aging: { ...aging, status: 'incomplete', unclassified: '99.11' } } }).includes('Exact overdue amount is unavailable'));
      for (const extra of [{loading:true},{error:'Unavailable'}]) assert.ok(!render({ report:{...report,aging},...extra }).includes('51.76'));
      for (const language of ['ta','si']) {
        const translated=renderToStaticMarkup(wrap(h(View,{...props,report:{...report,aging}}),language));
        assert.ok(!translated.includes('aging.')); assert.ok(!translated.includes('Reporting-only FIFO'));
      }
    });
    await t.test('existing export button is enabled only for the displayed valid report', () => {
      assert.doesNotMatch(render({ onExport() {} }).match(/<button[^>]*>/)[0], /disabled/);
      for (const extra of [{ loading: true }, { error: 'Unavailable' }, { exportBusy: true }, { report: undefined }, { businessId: 2 }]) {
        assert.match(render({ onExport() {}, ...extra }).match(/<button[^>]*>/)[0], /disabled/);
      }
      assert.ok(render({ exportBusy: true }).includes('Downloading report...'));
      assert.ok(render({ exportError: true }).includes('Report export failed.'));
      const called = [];
      function Capture() {
        const tree = View({ ...props, onExport: format => called.push(format) });
        function visit(node) {
          if (!node || typeof node !== 'object') return;
          if (node.type === 'button' && node.props.role === 'menuitem') node.props.onClick();
          for (const child of [node.props?.children].flat(Infinity)) visit(child);
        }
        visit(tree); return tree;
      }
      renderToStaticMarkup(wrap(h(Capture)));
      assert.deepEqual(called, ['csv', 'pdf']);
    });
    await t.test('CSV service requests an authenticated Blob with explicit business and applied dates', async () => {
      const { default: api } = await server.ssrLoadModule('/src/services/api.js');
      const { getFinancialReportCSV } = await server.ssrLoadModule('/src/services/shopOwnerReportsService.js');
      const original = api.get;
      const signal = new AbortController().signal;
      let request;
      const blob = new Blob(['\ufeffCSV'], { type: 'text/csv' });
      api.get = async (...args) => { request = args; return { headers: { 'content-type': 'text/csv; charset=utf-8' }, data: blob }; };
      try {
        assert.equal(await getFinancialReportCSV(1, { start_date: report.start_date, end_date: report.end_date }, signal), blob);
        assert.equal(request[0], '/shop-owner/reports/financial.csv');
        assert.deepEqual(request[1].params, { business_id: 1, start_date: report.start_date, end_date: report.end_date });
        assert.equal(request[1].responseType, 'blob'); assert.equal(request[1].signal, signal);
        api.get = async () => ({ headers: { 'content-type': 'application/json' }, data: new Blob(['error']) });
        await assert.rejects(getFinancialReportCSV(1, report, signal));
      } finally { api.get = original; }
    });
    await t.test('PDF service sends displayed dates and selected UI language; non-PDF responses fail', async () => {
      const { default: api } = await server.ssrLoadModule('/src/services/api.js');
      const { getFinancialReportPDF } = await server.ssrLoadModule('/src/services/shopOwnerReportsService.js');
      const original = api.get;
      const blob = new Blob(['%PDF-offline'], { type: 'application/pdf' });
      let request;
      api.get = async (...args) => { request = args; return { headers: { 'content-type': 'application/pdf' }, data: blob }; };
      try {
        assert.equal(await getFinancialReportPDF(1, report, undefined, 'ta'), blob);
        assert.equal(request[0], '/shop-owner/reports/financial.pdf');
        assert.deepEqual(request[1].params, { business_id: 1, start_date: report.start_date, end_date: report.end_date, language: 'ta' });
        api.get = async () => ({ headers: { 'content-type': 'application/json' }, data: new Blob(['error']) });
        await assert.rejects(getFinancialReportPDF(1, report));
      } finally { api.get = original; }
    });
  } finally { await server.close(); }
});
