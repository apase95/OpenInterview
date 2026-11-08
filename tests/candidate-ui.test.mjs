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
