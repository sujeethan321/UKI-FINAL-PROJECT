import test from 'node:test';
import assert from 'node:assert/strict';
import { validateApiUrl, validatePublicEnvironment } from '../src/utils/apiConfig.js';

test('local development API remains usable and trailing slash is normalized', () => {
  assert.equal(validateApiUrl('http://127.0.0.1:8000/api/v1/'), 'http://127.0.0.1:8000/api/v1');
});

test('production requires an explicit HTTPS API URL with one prefix', () => {
  assert.equal(validatePublicEnvironment({ VITE_API_URL: 'https://api.example.invalid/api/v1' }, true),
    'https://api.example.invalid/api/v1');
  for (const value of [undefined, '', '/api/v1', 'http://api.example.invalid/api/v1',
    'https://localhost/api/v1', 'https://127.0.0.1/api/v1', 'https://[::1]/api/v1',
    'https://localhost./api/v1', 'https://dev.localhost/api/v1', 'https://0.0.0.0/api/v1',
    'https://api.example.invalid/api/v1/api/v1', 'https://api.example.invalid/',
    'https://user:private@api.example.invalid/api/v1', 'https://api.example.invalid/api/v1?token=private']) {
    assert.throws(() => validateApiUrl(value, true));
  }
});

test('private or unreviewed VITE variables fail without revealing values', () => {
  for (const key of ['VITE_JWT_SECRET_KEY', 'VITE_MYSQL_PASSWORD', 'VITE_AI_KEY', 'VITE_OTHER']) {
    assert.throws(() => validatePublicEnvironment({
      VITE_API_URL: 'https://api.example.invalid/api/v1', [key]: 'private-sentinel',
    }, true), (error) => !error.message.includes('private-sentinel'));
  }
  assert.throws(() => validateApiUrl('https://user:private-sentinel@api.example.invalid/api/v1', true),
    (error) => !error.message.includes('private-sentinel'));
});
