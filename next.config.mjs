export function authBackend(value) {
  const url = new URL(value || 'http://127.0.0.1:8000');
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
      url.pathname !== '/' || url.search || url.hash) throw new Error('AUTH_BACKEND_URL must be an HTTP(S) origin without credentials.');
  return url.origin;
}

export default {
  output: 'standalone',
  async rewrites() {
    return [{ source: '/auth/:path*', destination: `${authBackend(process.env.AUTH_BACKEND_URL)}/auth/:path*` }];
  },
};
