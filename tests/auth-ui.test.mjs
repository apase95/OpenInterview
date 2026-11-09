import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const require = createRequire(import.meta.url);
const swc = require('next/dist/build/swc');
await swc.loadBindings();
function load(file = 'AuthCard') {
  const source = readFileSync(new URL(`../app/auth-ui/${file}.tsx`, import.meta.url), 'utf8');
  const output = swc.transformSync(source, { filename: 'AuthCard.tsx', jsc: { parser: { syntax: 'typescript', tsx: true }, transform: { react: { runtime: 'automatic' } } }, module: { type: 'commonjs' } }).code;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', output)(name => name.endsWith('.css') ? {} : name === './AccountControl' ? load('AccountControl') : require(name), module, module.exports);
  return module.exports;
}
test('both auth intents render one Google action and a fixed safe return path', () => {
  const { default: Card } = load();
  for (const intent of ['signin', 'signup']) {
    const html = renderToStaticMarkup(React.createElement(Card, { intent }));
    assert.match(html, /Continue with Google/);
    assert.match(html, new RegExp(`return_to=/roles&amp;intent=${intent}`));
    assert.equal((html.match(/class="google-button"/g) || []).length, 1);
    assert.doesNotMatch(html, /<input|password|HR|Admin|localStorage/);
    assert.match(html, /Google shares your name and email/);
    assert.match(html, intent === 'signin' ? /href="\/signup"/ : /href="\/login"/);
  }
});
test('query errors use fixed copy, never arbitrary provider text', () => {
  const { authError } = load();
  assert.match(authError('cancel'), /cancelled/);
  assert.match(authError('configuration'), /unavailable/);
  assert.equal(authError('<script>private</script>'), authError('unknown'));
  assert.equal(authError(null), '');
  assert.match(authError('state_invalid'), /expired/);
  for (const code of ['auth_unavailable', 'provider_unavailable', 'service_unavailable']) assert.match(authError(code), /unavailable/);
  assert.match(authError('identity_invalid'), /verified/);
});
test('proxy target is server-owned and rejects credentials or paths', async () => {
  const { authBackend, default: config } = await import('../next.config.mjs');
  assert.equal(authBackend(undefined), 'http://127.0.0.1:8000');
  assert.equal(authBackend('https://api.internal:8000'), 'https://api.internal:8000');
  for (const value of ['https://user:secret@api.internal', 'file:///tmp/api', 'https://api.internal/path', 'https://api.internal?target=elsewhere']) {
    assert.throws(() => authBackend(value));
  }
  const previous = process.env.AUTH_BACKEND_URL;
  try {
    process.env.AUTH_BACKEND_URL = 'http://127.0.0.1:8123';
    assert.deepEqual(await config.rewrites(), [{ source: '/auth/:path*', destination: 'http://127.0.0.1:8123/auth/:path*' }]);
  } finally {
    if (previous === undefined) delete process.env.AUTH_BACKEND_URL;
    else process.env.AUTH_BACKEND_URL = previous;
  }
});
test('account control uses cookie session and CSRF logout, with safe retry and unmount guard', () => {
  const source = readFileSync(new URL('../app/auth-ui/AccountControl.tsx', import.meta.url), 'utf8');
  assert.match(source, /fetch\('\/auth\/me', \{ credentials: 'same-origin', cache: 'no-store' \}/);
  assert.match(source, /fetch\('\/auth\/logout', \{ method: 'POST', credentials: 'include', headers: \{ 'X-CSRF-Token': account.csrf_token \}/);
  assert.match(source, /if \(!response.ok\) throw Error\(\);\s+setAccount\(null\)/);
  assert.match(source, /Could not sign out. Please try again/);
  assert.match(source, /return \(\) => \{ active = false; \}/);
  assert.doesNotMatch(source, /localStorage|document.cookie|dangerouslySetInnerHTML|setInterval/);
});
