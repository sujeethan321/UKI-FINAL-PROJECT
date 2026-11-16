import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

test('Vercel manifest uses frontend Vite build and guards assets/API from SPA fallback', async () => {
  const manifest = JSON.parse(await readFile(new URL('../vercel.json', import.meta.url), 'utf8'));
  assert.equal(manifest.framework, 'vite');
  assert.equal(manifest.installCommand, 'npm ci');
  assert.equal(manifest.buildCommand, 'npm run build');
  assert.equal(manifest.outputDirectory, 'dist');
  const rewrite = manifest.rewrites[0];
  const matches = new RegExp(`^${rewrite.source}$`);
  for (const path of ['/', '/login', '/customer/orders', '/driver/jobs', '/admin/dashboard']) {
    assert.ok(matches.test(path), path);
  }
  for (const path of ['/api', '/api/v1/health', '/assets/missing.js', '/assets', '/favicon.ico', '/missing.png']) {
    assert.ok(!matches.test(path), path);
  }
  assert.equal(rewrite.destination, '/index.html');
  assert.ok(!JSON.stringify(manifest).includes('localhost'));
});
