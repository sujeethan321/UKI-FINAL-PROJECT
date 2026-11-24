import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createReportCSVExporter, reportCSVFilename, reportPDFFilename, saveReportCSV } from '../src/utils/reportCSVExport.js';

const report = { business_id: 10, start_date: '2026-11-01', end_date: '2026-11-03' };
const blob = new Blob(['\ufeffCSV'], { type: 'text/csv' });

test('CSV download uses displayed business/dates and suppresses duplicate clicks', async () => {
  let resolve;
  const requests = [], saved = [];
  const exporter = createReportCSVExporter((...args) => {
    requests.push(args); return new Promise(done => { resolve = done; });
  }, (...args) => saved.push(args));
  const pending = exporter.start(report);
  assert.equal(exporter.getSnapshot().busy, true);
  await exporter.start(report);
  assert.equal(requests.length, 1);
  assert.equal(requests[0][0], 10);
  assert.deepEqual(requests[0][1], { start_date: '2026-11-01', end_date: '2026-11-03' });
  resolve(blob); await pending;
  assert.deepEqual(saved, [[blob, 'LankaPex-financial-10-2026-11-01-2026-11-03.csv']]);
  assert.deepEqual(exporter.getSnapshot(), { busy: false, error: false });
});

test('selection/session/unmount cancellation aborts and discards late private downloads', async () => {
  let resolve, signal;
  const saved = [];
  const exporter = createReportCSVExporter((_id, _range, value) => {
    signal = value; return new Promise(done => { resolve = done; });
  }, value => saved.push(value));
  const pending = exporter.start(report);
  exporter.cancel();
  assert.equal(signal.aborted, true);
  resolve(blob); await pending;
  assert.deepEqual(saved, []);
  assert.deepEqual(exporter.getSnapshot(), { busy: false, error: false });
});

test('failed requests never download and expose only generic error state', async () => {
  let saved = false;
  const exporter = createReportCSVExporter(async () => { throw new Error('PRIVATE_RESPONSE'); }, () => { saved = true; });
  await exporter.start(report);
  assert.equal(saved, false);
  assert.deepEqual(exporter.getSnapshot(), { busy: false, error: true });
  assert.ok(!JSON.stringify(exporter.getSnapshot()).includes('PRIVATE_RESPONSE'));
});

test('a superseded business download cannot replace the new selection download', async () => {
  const complete = [], saved = [];
  const exporter = createReportCSVExporter(() => new Promise(resolve => complete.push(resolve)),
    (_blob, filename) => saved.push(filename));
  const old = exporter.start(report);
  exporter.cancel();
  const current = exporter.start({ ...report, business_id: 20 });
  complete[0](blob); await old;
  assert.equal(exporter.getSnapshot().busy, true);
  assert.deepEqual(saved, []);
  complete[1](blob); await current;
  assert.deepEqual(saved, ['LankaPex-financial-20-2026-11-01-2026-11-03.csv']);
});

test('safe filenames reject untrusted IDs and header/filename input', () => {
  assert.match(reportCSVFilename(report), /^LankaPex-financial-10-/);
  for (const invalid of [{ business_id: '10' }, { business_id: -1 }, { start_date: '../../secret' }, { end_date: '2026-01-01\r\nX: value' }]) {
    assert.throws(() => reportCSVFilename({ ...report, ...invalid }));
  }
});

test('browser download removes its anchor and revokes the temporary Blob URL', () => {
  const prior = { document: globalThis.document, create: URL.createObjectURL, revoke: URL.revokeObjectURL, timer: globalThis.setTimeout };
  const calls = [];
  const anchor = { click() { calls.push('click'); }, remove() { calls.push('remove'); } };
  globalThis.document = { createElement: () => anchor, body: { appendChild() { calls.push('append'); } } };
  URL.createObjectURL = value => { assert.equal(value, blob); return 'blob:offline'; };
  URL.revokeObjectURL = value => calls.push(value);
  globalThis.setTimeout = callback => callback();
  try {
    saveReportCSV(blob, reportCSVFilename(report));
    assert.equal(anchor.download, reportCSVFilename(report));
    assert.deepEqual(calls, ['append', 'click', 'remove', 'blob:offline']);
  } finally {
    globalThis.document = prior.document; URL.createObjectURL = prior.create;
    URL.revokeObjectURL = prior.revoke; globalThis.setTimeout = prior.timer;
  }
});

test('PDF exports preserve applied selection and language, and share duplicate protection', async () => {
  let complete;
  const saved = [], calls = [];
  const exporter = createReportCSVExporter(() => { throw new Error('CSV must not run'); },
    (...args) => saved.push(args), (...args) => { calls.push(args); return new Promise(resolve => { complete = resolve; }); });
  const pending = exporter.start(report, 'pdf', 'si');
  await exporter.start(report, 'csv');
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], 10); assert.equal(calls[0][3], 'si');
  complete(blob); await pending;
  assert.equal(saved[0][1], 'LankaPex-financial-10-2026-11-01-2026-11-03-si.pdf');
  assert.throws(() => reportPDFFilename(report, '../unsafe'));
});

test('PDF failure and cancellation do not fall back to a CSV or download stale data', async () => {
  let saved = false;
  const exporter = createReportCSVExporter(async () => blob, () => { saved = true; }, async () => { throw new Error('private'); });
  await exporter.start(report, 'pdf', 'en');
  assert.equal(exporter.getSnapshot().error, true); assert.equal(saved, false);
});
