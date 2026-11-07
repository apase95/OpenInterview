// One owner survives pending browser/SDK operations until their late results are cleaned.
export class VoiceSession {
  constructor(io) { this.io = io; this.owner = null; }
  get busy() { return this.owner !== null; }
  start(consent, secret) {
    if (!consent || !secret || this.busy) return Promise.resolve();
    const owner = { secret, stopped: false };
    this.owner = owner;
    this.io.status('Starting');
    owner.pending = this.run(owner);
    return owner.pending;
  }
  async run(o) {
    try {
      o.lease = await this.io.issue(o.secret);
      if (o.stopped) return;
      const remaining = o.lease.ends_at * 1000 - Date.now();
      if (!Number.isFinite(remaining) || remaining <= 0 || remaining > 600000) throw Error();
      o.timer = setTimeout(() => { void this.end(); }, remaining);
      o.room = this.io.room(() => { if (!o.stopped) void this.end(); });
      await o.room.connect(o.lease);
      if (o.stopped) return;
      const track = await o.room.microphone();
      if (o.stopped) { track.stop(); return; }
      o.track = track;
      await o.room.publish(track);
      if (!o.stopped) this.io.status('Connected');
    } catch {
      o.stopped = true;
      this.io.status('Could not start voice. Local media stopped.');
    } finally {
      if (o.stopped) { this.stopLocal(o); await this.finish(o); }
    }
  }
  stopLocal(o) {
    o.stopped = true;
    clearTimeout(o.timer);
    o.track?.stop(); o.track = null;
    o.room?.stop();
  }
  async finish(o, keepalive = false) {
    if (o.ending) return o.ending;
    o.ending = (async () => {
      try {
        if (o.lease) await this.io.end(o.lease.session_id, o.secret, keepalive || o.keepalive);
        if (this.owner === o) this.owner = null;
        o.secret = '';
        this.io.status('Ended');
      } catch { this.io.status('Local media stopped. End not confirmed; press End to retry.'); }
    })();
    await o.ending; o.ending = null;
  }
  async end(keepalive = false) {
    const o = this.owner;
    if (!o) return;
    o.keepalive ||= keepalive;
    this.stopLocal(o);
    this.io.status('Stopping local media; cleaning up session');
    // Never abort issuance: its late session ID must still be ended.
    await o.pending;
    if (this.owner === o) await this.finish(o, keepalive);
  }
}
