'use client';

import { useEffect, useState } from 'react';

type Account = { user: { email: string; name?: string | null }; csrf_token: string };

export default function AccountControl() {
  const [account, setAccount] = useState<Account | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    void fetch('/auth/me', { credentials: 'same-origin', cache: 'no-store' })
      .then(async response => response.ok ? response.json() : null)
      .then(value => {
        if (active && typeof value?.user?.email === 'string' && typeof value?.csrf_token === 'string') setAccount(value);
      }).catch(() => {});
    return () => { active = false; };
  }, []);
  async function signout() {
    if (!account || busy) return;
    setBusy(true); setError('');
    try {
      const response = await fetch('/auth/logout', { method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': account.csrf_token } });
      if (!response.ok) throw Error();
      setAccount(null);
    } catch { setError('Could not sign out. Please try again.'); }
    finally { setBusy(false); }
  }
  if (!account) return <a className="inline-flex min-h-9 items-center text-sm leading-5 font-normal" href="/login">Sign in</a>;
  return <span className="inline-flex items-center gap-2.5 text-sm leading-normal"><span className="max-w-[140px] truncate" title={account.user.email}>{typeof account.user.name === 'string' && account.user.name || account.user.email}</span><button className="min-h-9 border-0 bg-transparent text-inherit disabled:opacity-55" disabled={busy} onClick={() => void signout()}>Sign out</button>{error && <span role="alert">{error}</span>}</span>;
}
