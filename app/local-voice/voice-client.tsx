'use client';

import { useEffect, useRef, useState } from 'react';
import { createLocalAudioTrack, LogLevel, Room, RoomEvent, setLogLevel, Track } from 'livekit-client';
import { VoiceSession } from './session.mjs';

const focus = 'focus-visible:outline-3 focus-visible:outline-focus focus-visible:outline-offset-3';
const button = `inline-flex items-center justify-center gap-1.5 min-h-[44px] rounded-lg border px-3 py-2 text-xs font-semibold leading-normal cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed enabled:hover:brightness-120 ${focus}`;
const audioButton = `${button} flex-auto border-[#79628d] bg-[#251b33] text-[#f3edff] aria-pressed:bg-[#47305f] aria-pressed:border-[#d6b3ff]`;
const consentLabel = 'my-4 flex cursor-pointer items-start gap-2.5 text-xs leading-normal text-[#cfc1df]';
const checkbox = `mt-0.5 h-[18px] w-[18px] shrink-0 accent-[#b887f4] ${focus}`;

const API = 'http://127.0.0.1:8000/local/voice/sessions';
const local = () => ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);

export default function VoiceClient() {
  const [secret, setSecret] = useState('');
  const [consent, setConsent] = useState(false);
  const [recordingConsent, setRecordingConsent] = useState(false);
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
      issue: async (key: string, recording: boolean) => (await post(API, key, JSON.stringify(recording ? { consent: true, recording_consent: true } : { consent: true }))).json(),
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

  return <main className="mx-auto my-8 w-[calc(100%-32px)] max-w-[480px] rounded-[20px] border border-[#493557] bg-[#140e1f] p-6 text-sm leading-normal text-[#f3edff] [@media(max-width:480px)]:my-4 [@media(max-width:480px)]:p-5">
    <h1 className="m-0 bg-[linear-gradient(#f3ecff,#be9be7)] bg-clip-text text-center text-[26px] leading-none tracking-[-.6px] text-transparent">Local voice test</h1>
    <div className="my-[22px] grid justify-items-center gap-3.5">
      <div className="w-[72px]" aria-hidden="true"><div className="flex h-12 items-center justify-center gap-4 rounded-2xl border-2 border-[#c9a8ed] bg-[#1a102a]"><span className="h-3 w-1.5 rounded-md bg-[#d9b5ff]" /><span className="h-3 w-1.5 rounded-md bg-[#d9b5ff]" /></div><div className="mx-auto mt-2 h-1 w-10 rounded-[50%] bg-[#765196]" /></div>
      <div className="flex items-center gap-2 font-semibold wrap-anywhere" role="status" aria-live="polite" aria-atomic="true"><span className="h-2 w-2 shrink-0 rounded-full bg-[#c4a1ef] data-[connected=true]:bg-[#8de5bf]" data-connected={status === 'Connected'} aria-hidden="true" />{status}</div>
    </div>
    <label className="block text-[13px] font-semibold">Local access secret <input className={`mt-1.5 block min-h-[44px] w-full rounded-lg border border-[#79628d] bg-[#0c0813] px-3 py-2.5 text-[#f3edff] ${focus}`} type="password" autoComplete="off" value={secret} disabled={busy} onChange={event => setSecret(event.target.value)} /></label>
    <label className={consentLabel}><input className={checkbox} type="checkbox" checked={consent} disabled={busy} onChange={event => setConsent(event.target.checked)} /><span>I consent to microphone use and sending audio/text to LiveKit, Deepgram, Google Gemini and ElevenLabs. Synthetic, non-sensitive data only.</span></label>
    <label className={consentLabel}><input className={checkbox} type="checkbox" checked={recordingConsent} disabled={busy} onChange={event => setRecordingConsent(event.target.checked)} /><span>Local debug recording (requires server flag): I consent to saving user and AI audio, finalized STT text, model input and AI text locally. Sensitive files remain until manually deleted. Leave unchecked when recording is disabled.</span></label>
    <div className="flex flex-wrap gap-2">
      <button className={`${button} flex-1 border-[#bd92ef] bg-brand text-[#f3edff]`} disabled={busy || !consent || !secret} onClick={() => {
        if (!local()) { setStatus('Loopback access required'); return; }
        setMicMuted(false); setSpeakerMuted(false); muted.current = false;
        void session.current?.start(consent, secret, recordingConsent); setSecret('');
      }}><span aria-hidden="true">▶</span> {status === 'Starting' ? 'Starting…' : 'Start session'}</button>
      <button className={`${button} flex-1 border-[#ab6479] bg-[#351823] text-[#ffd6e0]`} disabled={!busy} onClick={() => { void session.current?.end(); }}>{status.includes('End not confirmed') ? 'Retry End' : 'End'}</button>
    </div>
    <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Audio controls">
      <button className={audioButton} disabled={status !== 'Connected'} aria-pressed={micMuted} onClick={async () => {
        const room = roomRef.current; if (!room) return;
        try {
          for (const publication of room.localParticipant.audioTrackPublications.values()) {
            if (micMuted) await publication.track?.unmute(); else await publication.track?.mute();
          }
          setMicMuted(!micMuted);
        } catch { setStatus('Could not change microphone mute.'); }
      }}><span aria-hidden="true">◎</span> {micMuted ? 'Unmute microphone' : 'Mute microphone'}</button>
      <button className={audioButton} aria-pressed={speakerMuted} onClick={() => {
        muted.current = !muted.current; setSpeakerMuted(muted.current);
        audio.current?.querySelectorAll('audio').forEach(element => { element.muted = muted.current; });
      }}><span aria-hidden="true">◖</span> {speakerMuted ? 'Unmute speaker' : 'Mute speaker'}</button>
      <button className={audioButton} disabled={!busy} onClick={async () => { try { await roomRef.current?.startAudio(); } catch { setStatus('Audio blocked. Check browser permissions, then try Enable audio again.'); } }}>Enable audio</button>
    </div>
    <details className="mt-4 text-xs leading-normal text-muted"><summary className={`list-item min-h-[44px] cursor-pointer content-center text-[#d9b5ff] ${focus}`}>Data &amp; privacy</summary><p className="my-2">Microphone audio passes through LiveKit to Deepgram. Transcribed text goes to Google Gemini; speech text goes to ElevenLabs. Voice audio returns through LiveKit.</p><p className="my-2">No hiring evaluation. App recording and transcript persistence are off by default. When enabled on the server, separate recording consent is required. Replay is a worker-side estimate, not proof of browser playback. Providers may retain data under their terms and account settings; zero retention is not guaranteed.</p></details>
    <div ref={audio} />
  </main>;
}
