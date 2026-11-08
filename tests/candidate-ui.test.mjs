import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { renderToStaticMarkup } from 'react-dom/server';
import React from 'react';

const require = createRequire(import.meta.url);
const swc = require('next/dist/build/swc');
await swc.loadBindings();
function load(path) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8');
  const output = swc.transformSync(source, { filename: 'page.tsx', jsc: { parser: { syntax: 'typescript', tsx: true }, transform: { react: { runtime: 'automatic' } } }, module: { type: 'commonjs' } }).code;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', output)(name => name.endsWith('/AccountControl') ? load('../app/auth-ui/AccountControl.tsx') : require(name), module, module.exports);
  return module.exports;
}
function renderPage(path) {
  return renderToStaticMarkup(React.createElement(load(path).default));
}

test('candidate landing has branded navigation and an invitation link', () => {
  const html = renderPage('../app/roles/page.tsx');
  assert.match(html, /aria-label="OpenInterview home"/);
  assert.match(html, /href="#invitation"/);
  assert.match(html, /aria-current="page"/);
});

test('initial role selection has no premature progress or microphone request', () => {
  const html = renderPage('../app/roles/page.tsx');
  assert.doesNotMatch(html, /aria-label="Demo steps"/);
  assert.doesNotMatch(html, /SYNTHETIC ROLE|CANDIDATE EXPERIENCE|Check microphone/);
  assert.match(html, /required=""/);
  assert.match(html, /No live AI/);
});

test('main UI uses static Tailwind dimensions and scoped headings, including narrow layouts', () => {
  for (const path of ['../app/page.tsx', '../app/roles/page.tsx']) {
    const html = renderPage(path);
    assert.match(html, /<nav class="[^"]*min-h-12/);
    assert.match(html, /class="[^"]*size-6[^"]*overflow-hidden/);
    assert.match(html, /w-\[130\.4px\]/);
    assert.match(html, /\[@media\(max-width:760px\)\]:/);
  }
  const css = readFileSync(new URL('../app/globals.css', import.meta.url), 'utf8');
  assert.match(css, /@theme/);
  assert.doesNotMatch(css, /\.hero|\.candidate|\.demo-nav|h1\s*\{|@apply/);
  const auth = readFileSync(new URL('../app/auth-ui/AuthCard.tsx', import.meta.url), 'utf8');
  assert.doesNotMatch(auth, /import .*\.css/);
  assert.match(auth, /\[@media\(max-width:480px\)\]:pt-12/);
  assert.match(auth, /aria-disabled=\{pending\}/);
  for (const path of ['../app/page.tsx', '../app/roles/page.tsx', '../app/auth-ui/AccountControl.tsx', '../app/local-voice/voice-client.tsx']) {
    assert.doesNotMatch(readFileSync(new URL(path, import.meta.url), 'utf8'), /import .*\.css/);
  }
});
