import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const source = readFileSync(new URL('../app/local-voice/voice-client.tsx', import.meta.url), 'utf8');

test('voice card and controls use static touch-sized utilities without a CSS module', () => {
  assert.doesNotMatch(source, /styles\.|voice-client\.module\.css/);
  assert.equal(existsSync(new URL('../app/local-voice/voice-client.module.css', import.meta.url)), false);
  for (const utility of ['w-[calc(100%-32px)]', 'max-w-[480px]', '[@media(max-width:480px)]:p-5', 'min-h-[44px]', 'bg-brand', 'bg-[linear-gradient(#f3ecff,#be9be7)]', 'leading-none']) assert.ok(source.includes(utility), utility);
});

test('connected, pressed, disabled and keyboard focus states keep their bindings', () => {
  for (const value of ['data-[connected=true]:bg-[#8de5bf]', "data-connected={status === 'Connected'}", 'aria-pressed:bg-[#47305f]', 'aria-pressed:border-[#d6b3ff]', 'aria-pressed={micMuted}', 'aria-pressed={speakerMuted}', 'disabled:opacity-50', 'disabled:cursor-not-allowed', 'enabled:hover:brightness-120', 'focus-visible:outline-3', 'focus-visible:outline-focus', 'focus-visible:outline-offset-3', 'disabled={busy || !consent || !secret}', "disabled={status !== 'Connected'}"]) assert.ok(source.includes(value), value);
  assert.doesNotMatch(source, /<details[^>]*\bopen(?:[\s=>])/);
});
