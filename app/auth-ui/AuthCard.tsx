"use client";

import { useEffect, useState } from "react";
import { Header } from "../components/ui";
import { returnPath } from "../../lib/return-path";

export function authError(code: string | null): string {
  if (!code) return "";
  if (code === "cancel" || code === "access_denied")
    return "Sign-in was cancelled. You can try again.";
  if (
    [
      "configuration",
      "unavailable",
      "auth_unavailable",
      "provider_unavailable",
      "service_unavailable",
    ].includes(code)
  )
    return "Google sign-in is unavailable. Please try later.";
  if (code === "unverified_email" || code === "identity_invalid")
    return "Use a Google account with a verified email address.";
  if (["invalidstate", "invalid_state", "state_invalid"].includes(code))
    return "Sign-in expired. Please try again.";
  return "Could not sign in with Google. Please try again.";
}

export default function AuthCard({
  returnTo = "/roles",
}: {
  returnTo?: string;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    setError(
      authError(new URLSearchParams(window.location.search).get("error")),
    );
    const reset = () => setPending(false);
    window.addEventListener("pageshow", reset);
    return () => window.removeEventListener("pageshow", reset);
  }, []);
  return (
    <>
      <Header workspace="Welcome to OpenInterview" />
      <main className="mx-auto grid max-w-[1200px] items-start justify-items-center px-5 pt-24 pb-16">
        <section
          className="w-[min(100%,440px)] rounded-2xl border border-border bg-surface p-8"
          aria-labelledby="auth-title"
        >
          <h1
            className="mb-7 text-[32px] leading-tight tracking-normal text-ink bg-none"
            id="auth-title"
          >
            Sign in
          </h1>
          {error && <p role="alert">{error}</p>}
          <a
            className="flex min-h-12 w-full items-center justify-center gap-3 rounded-lg border border-border bg-page p-3 text-ink"
            href={`/api/auth/google/start?return_to=${encodeURIComponent(returnPath(returnTo))}`}
            aria-disabled={pending}
            onClick={(event) => {
              if (pending) event.preventDefault();
              else setPending(true);
            }}
          >
            {pending ? "Opening Google…" : "Continue with Google"}
          </a>
          <p className="mt-4 text-sm text-muted">
            Google shares your name and verified email to match your account.
            New accounts are candidates.
          </p>
          <details className="mt-5 text-sm text-muted">
            <summary>Account terms & privacy</summary>
            <p className="mt-3">
              Use the account invited by your recruiter. Signing in does not
              join an interview or provide interview consent. HR and Admin
              access require a separate confirmed server grant.
            </p>
            <p className="mt-3">
              This workspace currently supports preparation only. No interview
              audio, transcripts or reports are collected. Approved retention
              periods, policy version and privacy contact must be supplied
              before live interviews are enabled.
            </p>
          </details>
        </section>
      </main>
    </>
  );
}
