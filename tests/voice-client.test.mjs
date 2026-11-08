import { test } from 'node:test';
import assert from 'node:assert/strict';
import { VoiceSession } from '../app/local-voice/session.mjs';

const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function setup(overrides = {}) {
  const calls = [];
  const room = { connect: async () => {}, stop: () => calls.push('stop'), microphone: async () => ({ stop: () => calls.push('track-stop') }), publish: async () => {} };
  const client = new VoiceSession({ issue: async () => ({ session_id: 'test', ends_at: Date.now() / 1000 + 60 }), end: async () => calls.push('end'), room: () => room, status: () => {}, ...overrides });
  return { client, calls, room };
}
test('consent gate and happy lifecycle', async () => {
  let issued = 0;
  const { client, calls } = setup({ issue: async () => { issued++; return { session_id: 'test', ends_at: Date.now() / 1000 + 60 }; } });
  await client.start(false, 'secret'); assert.equal(issued, 0);
  await client.start(true, 'secret'); assert.equal(issued, 1);
  await client.end(); assert.deepEqual(calls, ['track-stop', 'stop', 'end']);
});
test('recording consent travels with issuance; unapproved recording stops before media', async () => {
  let consent;
  const { client, calls } = setup({ issue: async (_secret, recording) => {
    consent = recording;
    return { session_id: 'test', recording: true, ends_at: Date.now() / 1000 + 60 };
  } });
  await client.start(true, 'secret');
  assert.equal(consent, false); assert.deepEqual(calls, ['end']);
  await client.start(true, 'secret', true);
  assert.equal(consent, true);
  await client.end();
});
test('End wins late issuance, connection and microphone; failed End can retry', async () => {
  for (const phase of ['issue', 'connect', 'microphone']) {
    const gate = deferred(); const entered = deferred();
    const { client, calls, room } = setup();
    if (phase === 'issue') client.io.issue = async () => { entered.resolve(); return gate.promise; };
    else room[phase] = async () => { entered.resolve(); return gate.promise; };
    const start = client.start(true, 'secret'); await entered.promise;
    const end = client.end();
    assert.equal(client.busy, true);
    gate.resolve(phase === 'issue' ? { session_id: 'late', ends_at: Date.now() / 1000 + 60 } : phase === 'microphone' ? { stop: () => calls.push('late-track-stop') } : undefined);
    await Promise.all([start, end]);
    assert.equal(client.busy, false); assert.ok(calls.includes('end'));
    if (phase === 'microphone') assert.ok(calls.includes('late-track-stop'));
  }
  let fail = true;
  const { client } = setup({ end: async () => { if (fail) throw Error('private'); } });
  await client.start(true, 'secret'); await client.end(); assert.equal(client.busy, true);
  fail = false; await client.end(); assert.equal(client.busy, false);
});
test('disconnect cleanup and keepalive End retain ownership during issuance', async () => {
  let disconnected;
  const first = setup();
  first.client.io.room = callback => { disconnected = callback; return first.room; };
  await first.client.start(true, 'secret');
  disconnected(); await first.client.end();
  assert.equal(first.client.busy, false); assert.ok(first.calls.includes('end'));
  const gate = deferred(); let keepalive;
  const { client } = setup({ issue: () => gate.promise, end: async (_id, _key, flag) => { keepalive = flag; } });
  const start = client.start(true, 'secret'); const end = client.end(true);
  await client.start(true, 'other');
  gate.resolve({ session_id: 'late', ends_at: Date.now() / 1000 + 60 });
  await Promise.all([start, end]); assert.equal(keepalive, true); assert.equal(client.busy, false);
});
