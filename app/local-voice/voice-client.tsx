'use client';

import { useEffect, useRef, useState } from 'react';
import { createLocalAudioTrack, LogLevel, Room, RoomEvent, setLogLevel, Track } from 'livekit-client';
import { VoiceSession } from './session.mjs';
import styles from './voice-client.module.css';

const API = 'http://127.0.0.1:8000/local/voice/sessions';
const local = () => ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);

export default function VoiceClient() {
  const [secret, setSecret] = useState('');
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState('Ready');
  const [busy, setBusy] = useState(false);
  const [micMuted, setMicMuted] = useState(false);
  const [speakerMuted, setSpeakerMuted] = useState(false);
  const session = useRef<VoiceSession | null>(null);
  const roomRef = useRef<Room | null>(null);
  const audio = useRef<HTMLDivElement>(null);
  const muted = useRef(false);

  useEffect(() => {
    let mounted = true;
    setLogLevel(LogLevel.silent);
    const post = async (url: string, key: string, body?: string, keepalive = false) => {
      if (!local()) throw Error();
      const response = await fetch(url, { method: 'POST', headers: { Authorization: `Bearer ${key}`, ...(body ? { 'Content-Type': 'application/json' } : {}) }, body, cache: 'no-store', credentials: 'omit', keepalive });
      if (!response.ok) throw Error();
      return response;
    };
    const client = new VoiceSession({
      issue: async (key: string) => (await post(API, key, JSON.stringify({ consent: true }))).json(),
      end: async (id: string, key: string, keepalive: boolean) => { await post(`${API}/${encodeURIComponent(id)}/end`, key, undefined, keepalive); },
      status: (text: string) => { if (mounted) { setStatus(text); setBusy(client.busy); } },
      room: (disconnected: () => void) => {
        const room = new Room({ reconnectPolicy: { nextRetryDelayInMs: () => null } });
        roomRef.current = room;
        const elements = new Set<HTMLMediaElement>();
        let stopped = false;
        room.on(RoomEvent.TrackPublished, (publication) => { if (publication.kind === Track.Kind.Audio) publication.setSubscribed(true); });
        room.on(RoomEvent.TrackSubscribed, (track) => {
          if (stopped || track.kind !== Track.Kind.Audio) return;
          const element = track.attach(); element.muted = muted.current;
          elements.add(element); audio.current?.appendChild(element);
        });
        room.on(RoomEvent.TrackUnsubscribed, track => { for (const element of track.detach()) { elements.delete(element); element.remove(); } });
        room.on(RoomEvent.Disconnected, disconnected);
        return {
          connect: async (lease: { url: string; token: string }) => {
            await room.connect(lease.url, lease.token, { autoSubscribe: false });
            if (stopped) { await room.disconnect(); return; }
            for (const participant of room.remoteParticipants.values()) for (const publication of participant.trackPublications.values()) if (publication.kind === Track.Kind.Audio) publication.setSubscribed(true);
          },
          microphone: () => createLocalAudioTrack({ echoCancellation: true, noiseSuppression: true }),
          publish: async (track: Awaited<ReturnType<typeof createLocalAudioTrack>>) => { await room.localParticipant.publishTrack(track); },
          stop: () => {
            stopped = true;
            room.removeAllListeners();
            for (const publication of room.localParticipant.trackPublications.values()) publication.track?.stop();
            for (const element of elements) { element.pause(); element.srcObject = null; element.remove(); }
            elements.clear();
            void room.disconnect().catch(() => {});
            if (roomRef.current === room) roomRef.current = null;
          },
        };
      },
    });
    session.current = client;
    const leave = () => { void client.end(true); };
    window.addEventListener('pagehide', leave);
    return () => { mounted = false; window.removeEventListener('pagehide', leave); leave(); session.current = null; };
  }, []);

  return <main className={styles.console}>
    <h1>Local voice test</h1>
    <div className={styles.stage}>
      <div className={styles.robot} aria-hidden="true"><div className={styles.face}><span /><span /></div><div className={styles.robotBase} /></div>
      <div className={styles.status} role="status" aria-live="polite" aria-atomic="true"><span className={styles.dot} data-connected={status === 'Connected'} aria-hidden="true" />{status}</div>
    </div>
    <label className={styles.field}>Local access secret <input type="password" autoComplete="off" value={secret} disabled={busy} onChange={event => setSecret(event.target.value)} /></label>
    <label className={styles.consent}><input type="checkbox" checked={consent} disabled={busy} onChange={event => setConsent(event.target.checked)} /><span>I consent to microphone use and sending audio/text to LiveKit, Deepgram, Google Gemini and ElevenLabs. Synthetic, non-sensitive data only.</span></label>
    <div className={styles.sessionActions}>
      <button className={styles.primary} disabled={busy || !consent || !secret} onClick={() => {
        if (!local()) { setStatus('Loopback access required'); return; }
        setMicMuted(false); setSpeakerMuted(false); muted.current = false;
        void session.current?.start(consent, secret); setSecret('');
      }}><span aria-hidden="true">▶</span> {status === 'Starting' ? 'Starting…' : 'Start session'}</button>
      <button className={styles.danger} disabled={!busy} onClick={() => { void session.current?.end(); }}>{status.includes('End not confirmed') ? 'Retry End' : 'End'}</button>
    </div>
    <div className={styles.audioActions} role="group" aria-label="Audio controls">
      <button disabled={status !== 'Connected'} aria-pressed={micMuted} onClick={async () => {
        const room = roomRef.current; if (!room) return;
        try {
          for (const publication of room.localParticipant.audioTrackPublications.values()) {
            if (micMuted) await publication.track?.unmute(); else await publication.track?.mute();
          }
          setMicMuted(!micMuted);
        } catch { setStatus('Could not change microphone mute.'); }
      }}><span aria-hidden="true">◎</span> {micMuted ? 'Unmute microphone' : 'Mute microphone'}</button>
      <button aria-pressed={speakerMuted} onClick={() => {
        muted.current = !muted.current; setSpeakerMuted(muted.current);
        audio.current?.querySelectorAll('audio').forEach(element => { element.muted = muted.current; });
      }}><span aria-hidden="true">◖</span> {speakerMuted ? 'Unmute speaker' : 'Mute speaker'}</button>
      <button disabled={!busy} onClick={async () => { try { await roomRef.current?.startAudio(); } catch { setStatus('Audio blocked. Check browser permissions, then try Enable audio again.'); } }}>Enable audio</button>
    </div>
    <details className={styles.privacy}><summary>Data &amp; privacy</summary><p>Microphone audio passes through LiveKit to Deepgram. Transcribed text goes to Google Gemini; speech text goes to ElevenLabs. Voice audio returns through LiveKit.</p><p>No hiring evaluation, app recording or transcript persistence. Providers may retain data under their terms and account settings; zero retention is not guaranteed.</p></details>
    <div ref={audio} />
  </main>;
}
