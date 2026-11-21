export function billingRedirect(value, portal = false) {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.hostname !== (portal ? 'billing.stripe.com' : 'checkout.stripe.com') ||
      url.username || url.password || (url.port && url.port !== '443')) throw new Error('Invalid billing redirect');
  return url.href;
}

export function checkoutRequestKey(storage, businessId, plan, interval, randomId) {
  const key = `lankapex-checkout:${businessId}:${plan}:${interval}`;
  let value = storage.getItem(key);
  if (!value) {
    value = randomId();
    storage.setItem(key, value);
  }
  return value;
}
