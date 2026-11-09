'use client';

import { useEffect, useRef, useState } from 'react';
import AccountControl from '../auth-ui/AccountControl';

const API = process.env.NEXT_PUBLIC_CANDIDATE_API_BASE || 'http://127.0.0.1:8000';
type Role = { role_id: string; name: string };
type Room = { room_id: string; role_id: string; expires_at: number };
type Session = { session_id: string; status: string; expires_at: number };

const card = 'rounded-2xl border border-border bg-surface p-7 [@media(max-width:760px)]:p-[22px] [&_p]:text-[#cfc4dc]';
const narrowCard = `${card} mx-auto my-6 max-w-[720px]`;
const button = 'inline-flex min-h-[46px] items-center justify-center gap-3.5 rounded-[10px] border px-[27px] py-3.5 text-sm leading-normal disabled:opacity-55';
const primary = `${button} mt-4 min-w-[158px] border-[#b28bdd] bg-brand`;
const secondary = `${button} mt-4 border-[#89709f] bg-[#1a1227]`;
const eyebrow = 'text-xs font-bold tracking-[1.4px] text-[#d0b2f7]';
const actions = 'my-5 flex flex-wrap justify-start gap-3.5';
const textLink = 'm-5 inline-block underline';

export default function Roles() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [room, setRoom] = useState<Room | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [step, setStep] = useState('roles');
  const [invitation, setInvitation] = useState('');
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [mic, setMic] = useState('Microphone is off.');
  const stream = useRef<MediaStream | null>(null);
  const generation = useRef(0);
  const title = useRef<HTMLHeadingElement>(null);
  const stop = () => {
    generation.current++;
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
  };
  async function api(path: string, body?: object): Promise<any> {
    const response = await fetch(`${API}/demo${path}`, {
      method: body ? 'POST' : 'GET', credentials: 'omit', cache: 'no-store',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) throw Error(response.status === 404 ? 'Demo unavailable, expired or not found. Ask for a new demo room.' : response.status === 429 ? 'Demo is full. Please try later.' : 'Could not connect. Check the demo API and try again.');
    return response.json();
  }
  async function action(work: () => Promise<void>) {
    setBusy(true); setError('');
    try { await work(); } catch (e) { setError(e instanceof Error ? e.message : 'Please try again.'); }
    finally { setBusy(false); }
  }
  const load = () => action(async () => { setRoles(await api('/roles')); });
  useEffect(() => { void load(); const leave = () => stop(); window.addEventListener('pagehide', leave); return () => { stop(); window.removeEventListener('pagehide', leave); }; }, []);
  useEffect(() => { if (step !== 'roles') title.current?.focus(); }, [step]);
  useEffect(() => {
    if (!session || session.status === 'ended') return;
    const timer = setTimeout(() => { stop(); setMic('Microphone is off.'); setError('This demo has expired. Start again from roles.'); setStep('expired'); }, Math.max(0, session.expires_at * 1000 - Date.now()));
    return () => clearTimeout(timer);
  }, [session]);
  async function checkMic() {
    stop(); const current = generation.current;
    if (!navigator.mediaDevices?.getUserMedia) { setMic('Microphone testing is not supported. Use a secure browser, or continue without it.'); return; }
    setMic('Waiting for browser permission…');
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (current !== generation.current) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current = media; setMic('Microphone is available. No audio is recorded, played back or uploaded.');
    } catch { if (current === generation.current) setMic('Microphone unavailable or permission denied. Check browser settings, or continue without it.'); }
  }
  const openRoom = (value: Room) => { stop(); setRoom(value); setAck(false); setSession(null); setStep('room'); };
  const finish = () => { stop(); setMic('Microphone is off.'); void action(async () => {
    const value = await api(`/sessions/${session!.session_id}/end`, {});
    setSession(value); setStep('finished');
  }); };
  return <>
    <header className="border-b border-border"><nav className="relative mx-auto flex min-h-12 max-w-[1328px] items-center justify-between gap-6 px-6 [@media(max-width:760px)]:flex-wrap [@media(max-width:760px)]:gap-3 [@media(max-width:760px)]:px-4 [@media(max-width:760px)]:py-2" aria-label="Main navigation"><a className="inline-flex shrink-0 items-center gap-2.5 text-[18px] font-semibold [@media(max-width:760px)]:text-base" href="/" aria-label="OpenInterview home"><span className="block size-6 overflow-hidden" aria-hidden="true"><img className="block h-6 w-[130.4px] max-w-none" src="/images/logo.svg" width="163" height="30" alt="" /></span><span>OpenInterview</span></a><span className="absolute left-1/2 -translate-x-1/2 text-sm leading-normal text-[#bcb1cb] [@media(max-width:760px)]:hidden">Candidate workspace</span><div className="flex items-center gap-[30px] [@media(max-width:760px)]:gap-4"><a className="inline-flex min-h-9 items-center text-sm leading-5 font-normal text-muted aria-[current=page]:text-ink aria-[current=page]:underline aria-[current=page]:underline-offset-8" href="/roles" aria-current="page">Roles</a><a className="inline-flex min-h-9 items-center text-sm leading-5 font-normal" href={step === 'roles' ? '#invitation' : '/roles#invitation'}>Invitation</a><AccountControl /></div></nav></header>
    <main className="mx-auto max-w-[1328px] px-6 pt-12 pb-20 [@media(max-width:760px)]:px-4 [@media(max-width:760px)]:pt-8 [@media(max-width:760px)]:pb-14 [&_h2]:my-3 [&_h2]:text-[23px] [&_p]:leading-[1.65]">
      <h1 className="mb-4 text-[clamp(30px,4vw,40px)] leading-[1.15] tracking-[-1px] text-ink" ref={title} tabIndex={-1}>{step === 'roles' ? 'Find your conversation.' : step === 'room' ? 'Before we begin.' : step === 'mic' ? 'A quick mic check' : step === 'interview' ? 'Make yourself comfortable.' : step === 'finished' ? 'You’re all done.' : 'Demo expired'}</h1>
      <p className="mb-8 text-base text-muted">{step === 'roles' ? 'Choose a role to explore the demo. No live AI or real hiring interview.' : 'Demo only. No audio is recorded or uploaded.'}</p>
      {step !== 'roles' && <ol className="mb-7 flex w-fit list-none flex-wrap gap-1 rounded-[10px] border border-border p-1 text-sm leading-normal text-[#bcb1cb]" aria-label="Demo steps">{['Acknowledgement', 'Mic check', 'Preparation', 'Finish'].map((text, i) => <li className="rounded-md px-4 py-2.5 aria-[current]:bg-[#271b36] aria-[current]:text-[#f0dbff] [@media(max-width:760px)]:px-2.5 [@media(max-width:760px)]:py-2" key={text} aria-current={i === ['room', 'mic', 'interview', 'finished'].indexOf(step) ? 'step' : undefined}>{i + 1}. {text}</li>)}</ol>}
      {error && <div className="mb-5 rounded-[10px] border border-[#e4b684] p-[18px] text-[#ffe1bd]" role="alert">{error} {step === 'roles' && <button onClick={() => void load()} disabled={busy}>Retry loading roles</button>}</div>}
      <div role="status" aria-live="polite">{busy ? 'Loading…' : ''}</div>
      {step === 'roles' && <>
        <section aria-label="Demo roles" className="grid grid-cols-3 gap-5 [@media(max-width:760px)]:grid-cols-1">{roles.map(role => <article className={`${card} hover:border-[#9870c2] focus-within:border-[#9870c2]`} key={role.role_id}><div className="flex min-h-[60px] items-center gap-4 [&_h2]:my-0!"><svg className="shrink-0 rounded-xl border border-border p-[9px] text-[#d0b2f7]" width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" aria-hidden="true"><rect x="4" y="6" width="16" height="13" rx="2" /><path d="M9 6V4h6v2M4 11h16M10 11v3h4v-3" /></svg><h2>{role.name}</h2></div><button className="mt-[22px] flex min-h-11 w-full justify-between border-0 border-t border-border bg-transparent pt-5 text-left text-[#d0b2f7] disabled:opacity-55" aria-label={`Explore ${role.name} demo`} disabled={busy} onClick={() => void action(async () => openRoom(await api('/rooms', { role_id: role.role_id })))}>Explore demo <span aria-hidden="true">↗</span></button></article>)}</section>
        {!busy && !error && !roles.length && <p>No demo roles are available.</p>}
        <form id="invitation" className={`${card} mt-8 [&_h2]:mt-0!`} onSubmit={e => { e.preventDefault(); void action(async () => openRoom(await api(`/rooms/${encodeURIComponent(invitation.trim())}`))); }}><h2>Have an invitation?</h2><p id="code-help">Use a code from another demo tester. Keep it private.</p><label htmlFor="room-code">Demo room code</label><input className="mt-2.5 block w-[min(100%,560px)] rounded-lg border border-[#9a81ad] bg-page p-[13px] text-white" id="room-code" aria-describedby="code-help" value={invitation} maxLength={80} pattern="[A-Za-z0-9_-]{43}" required autoComplete="off" onChange={e => setInvitation(e.target.value)} /><button className={secondary} disabled={busy}>Open demo room</button></form>
      </>}
      {step === 'room' && room && <section className={narrowCard}><p className={eyebrow}>{roles.find(r => r.role_id === room.role_id)?.name || 'Demo role'}</p><h2>A practice journey, on your terms.</h2><p>This is not an official invitation, legal consent, or a hiring assessment. Live AI integration is not part of this demo. No audio, transcript or report is sent to a server.</p><p>Optional microphone testing happens only in this browser after you press Check microphone. You can skip it.</p><details><summary>Share this demo room</summary><p>Code expires after 30 minutes or an API restart. Anyone with this code can access this synthetic room.</p><code className="[overflow-wrap:anywhere] select-all">{room.room_id}</code></details><label className="mt-6 flex items-start gap-3 leading-[1.6]"><input className="mt-1.5 size-[18px] shrink-0" type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} />I understand and want to take part in this demo.</label><button className={primary} disabled={busy || !ack} onClick={() => void action(async () => { const value = await api(`/rooms/${room.room_id}/sessions`, { acknowledged: true }); setSession(value); setStep(value.status === 'ended' ? 'finished' : 'mic'); })}>Continue to mic check</button><a className={textLink} href="/roles">Not now — back to roles</a></section>}
      {step === 'mic' && <section className={narrowCard}><h2>Check permission. Keep audio local.</h2><p>No recording or upload. This checks access only, not audio quality. Mic testing is optional.</p><p role="status">{mic}</p><div className={actions}><button className={secondary} onClick={() => void checkMic()}>Check microphone</button><button className={secondary} onClick={() => { stop(); setMic('Microphone is off.'); }}>Stop microphone</button></div><button className={primary} disabled={busy} onClick={() => { stop(); void action(async () => { const value = await api(`/sessions/${session!.session_id}`); setSession(value); setStep(value.status === 'ended' ? 'finished' : 'interview'); }); }}>Continue without audio</button></section>}
      {step === 'interview' && <section className={`${card} mx-auto max-w-[800px] text-center`}><img className="mx-auto mt-4 mb-8 block" src="/images/robot.svg" width="200" height="200" alt="Static interview robot illustration" /><p className={eyebrow}>PREPARATION ONLY · MICROPHONE OFF</p><h2>There is no live AI here.</h2><p>In a future interview, speech will be in Vietnamese. For now, take a moment to think about how you would introduce yourself. No answer is collected.</p><button className={primary} disabled={busy} onClick={finish}>Finish demo</button><p>If ending fails, your microphone stays off. Use Finish demo again to retry.</p></section>}
      {(step === 'finished' || step === 'expired') && <section className={narrowCard}><h2>{step === 'finished' ? 'Demo finished' : 'Start fresh when you’re ready'}</h2><p>No interview took place. No recording, AI response, evaluation or report was created.</p><a className={primary} href="/roles">Back to roles</a></section>}
      {step === 'mic' && <button className={textLink} disabled={busy} onClick={finish}>End demo now</button>}
    </main>
  </>;
}
