'use client';

import { useEffect, useState } from 'react';
import AccountControl from './AccountControl';

export function authError(code: string | null): string {
  if (!code) return '';
  if (code === 'cancel' || code === 'access_denied') return 'Sign-in was cancelled. You can try again.';
  if (['configuration', 'unavailable', 'auth_unavailable', 'provider_unavailable', 'service_unavailable'].includes(code)) return 'Google sign-in is unavailable. Please try later.';
  if (code === 'unverified_email' || code === 'identity_invalid') return 'Use a Google account with a verified email address.';
  if (['invalidstate', 'invalid_state', 'state_invalid'].includes(code)) return 'Sign-in expired. Please try again.';
  return 'Could not sign in with Google. Please try again.';
}

export default function AuthCard({ intent }: { intent: 'signin' | 'signup' }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    setError(authError(new URLSearchParams(window.location.search).get('error')));
    const reset = () => setPending(false);
    window.addEventListener('pageshow', reset);
    return () => window.removeEventListener('pageshow', reset);
  }, []);
  const signup = intent === 'signup';
  return <>
    <header className="border-b border-border"><nav className="relative mx-auto flex min-h-12 max-w-[1328px] items-center justify-between gap-6 px-6 [@media(max-width:760px)]:flex-wrap [@media(max-width:760px)]:gap-3 [@media(max-width:760px)]:px-4 [@media(max-width:760px)]:py-2" aria-label="Main navigation">
      <a className="inline-flex shrink-0 items-center gap-2.5 text-[18px] font-semibold [@media(max-width:760px)]:text-base" href="/" aria-label="OpenInterview home"><span className="block size-6 overflow-hidden" aria-hidden="true"><img className="block h-6 w-[130.4px] max-w-none" src="/images/logo.svg" alt="" width="130.4" height="24" /></span><span>OpenInterview</span></a>
      <div className="flex items-center gap-[30px] [@media(max-width:760px)]:gap-4"><a className="inline-flex min-h-9 items-center text-sm leading-5 font-normal text-muted" href="/roles">Roles</a><a className="inline-flex min-h-9 items-center text-sm leading-5 font-normal" href="/">Back to home</a><AccountControl /></div>
    </nav></header>
    <main className="mx-auto grid max-w-[1200px] items-start justify-items-center px-5 pt-24 pb-16 [@media(max-width:480px)]:pt-12"><section className="w-[min(100%,420px)] rounded-2xl border border-border bg-surface p-8 [@media(max-width:480px)]:p-6 [&_p]:text-sm [&_p]:leading-[1.6]" aria-labelledby="auth-title">
      <h1 className="mb-7 text-[32px] leading-[1.2] tracking-[-.5px] text-ink" id="auth-title">{signup ? 'Sign up' : 'Sign in'}</h1>
      {error && <p role="alert" className="text-[#ffe1bd]">{error}</p>}
        <a className="flex min-h-12 w-full items-center justify-center gap-3 rounded-lg border border-[#bda3df] bg-[#1a1227] p-3 text-ink no-underline hover:bg-[#291b3c]" href={`/auth/google/start?return_to=/roles&intent=${intent}`} aria-disabled={pending} onClick={event => {
          if (pending) event.preventDefault();
          else setPending(true);
        }}>
          <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5Z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6C44.4 38.02 46.98 31.86 46.98 24.55Z"/><path fill="#FBBC05" d="M10.53 28.59a14.4 14.4 0 0 1 0-9.18l-7.98-6.19a24 24 0 0 0 0 21.56l7.98-6.19Z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.9-5.8l-7.73-6c-2.15 1.45-4.92 2.3-8.17 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48Z"/></svg>
          {pending ? 'Opening Google…' : 'Continue with Google'}
        </a>
      <p className="mt-2 text-muted">Google shares your name and email.</p>
      {signup && <p className="mt-2 text-muted">New accounts are candidate accounts.</p>}
      <p>{signup ? 'Already have an account?' : 'New here?'} <a className="text-[#d1b7ff] underline underline-offset-[3px]" href={signup ? '/login' : '/signup'}>{signup ? 'Sign in' : 'Sign up'}</a></p>
    </section></main>
  </>;
}
