// Shared by the Vite build and Axios. Values are deliberately omitted from errors.
export function validateApiUrl(value, production = false) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error('VITE_API_URL must be an absolute API URL ending in /api/v1');
  }
  const hostname = url.hostname.toLowerCase().replace(/\.$/, '');
  const local = ['localhost', '0.0.0.0', '127.0.0.1', '[::1]', '[::]'].includes(hostname)
    || hostname.endsWith('.localhost') || hostname.startsWith('127.');
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password
    || url.search || url.hash || url.pathname.replace(/\/$/, '') !== '/api/v1'
    || (production && (url.protocol !== 'https:' || local))) {
    throw new Error('VITE_API_URL requires /api/v1 exactly once; production requires HTTPS and a non-local host');
  }
  return url.href.replace(/\/$/, '');
}

export function validatePublicEnvironment(env, production = false) {
  if (Object.keys(env).some((name) => name.startsWith('VITE_') && name !== 'VITE_API_URL')) {
    throw new Error('Only VITE_API_URL is approved for public frontend configuration');
  }
  return validateApiUrl(env.VITE_API_URL, production);
}
