import { test } from 'node:test';
import assert from 'node:assert/strict';
import { billingRedirect, checkoutRequestKey } from '../src/utils/billing.js';

test('billing redirects accept only the exact hosted HTTPS Stripe surfaces', () => {
  assert.equal(billingRedirect('https://checkout.stripe.com/c/pay/cs_test_x'), 'https://checkout.stripe.com/c/pay/cs_test_x');
  assert.equal(billingRedirect('https://billing.stripe.com/p/test', true), 'https://billing.stripe.com/p/test');
  for (const url of ['javascript:alert(1)', 'http://checkout.stripe.com/x', 'https://checkout.stripe.com.evil/x',
    'https://user@checkout.stripe.com/x', 'https://billing.stripe.com/x', 'https://checkout.stripe.com:444/x']) {
    assert.throws(() => billingRedirect(url));
  }
});

test('duplicate clicks and reloads retain the same key; business and plan scopes differ', () => {
  const data = new Map();
  const storage = { getItem: key => data.get(key), setItem: (key, value) => data.set(key, value) };
  let serial = 0;
  const next = () => `offline-request-${++serial}`;
  const key = checkoutRequestKey(storage, 10, 'PRO', 'month', next);
  assert.equal(checkoutRequestKey(storage, 10, 'PRO', 'month', next), key);
  assert.notEqual(checkoutRequestKey(storage, 20, 'PRO', 'month', next), key);
  assert.notEqual(checkoutRequestKey(storage, 10, 'BUSINESS', 'month', next), key);
  assert.notEqual(checkoutRequestKey(storage, 10, 'PRO', 'year', next), key);
  assert.equal(serial, 4);
});
