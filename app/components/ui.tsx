"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import s from "./workspace.module.css";
import Logo from "./logo";
import AccountControl from "../auth-ui/AccountControl";
import ThemeToggle from "./theme-toggle";

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    arrow: (
      <>
        <path d="M5 12h14M13 6l6 6-6 6" />
      </>
    ),
    mic: (
      <>
        <rect x="9" y="2" width="6" height="12" rx="3" />
        <path d="M5 10v2a7 7 0 0014 0v-2M12 19v3M8 22h8" />
      </>
    ),
    speaker: (
      <>
        <path d="M11 4L5 9H2v6h3l6 5zM15 8a6 6 0 010 8M18 4a11 11 0 010 16" />
      </>
    ),
    end: (
      <>
        <path d="M4 15v-4c4-4 12-4 16 0v4h-5v-4H9v4z" />
      </>
    ),
    layers: (
      <>
        <path d="M12 3L2 8l10 5 10-5zM2 12l10 5 10-5M2 16l10 5 10-5" />
      </>
    ),
    code: (
      <>
        <path d="M8 5L2 12l6 7M16 5l6 7-6 7M14 3l-4 18" />
      </>
    ),
    window: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M3 8h18M8 8v13" />
      </>
    ),
    database: (
      <>
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0" />
      </>
    ),
    sparkle: (
      <>
        <path d="M12 2l3 7 7 3-7 3-3 7-3-7-7-3z" />
      </>
    ),
    branch: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="2" />
        <rect x="14" y="14" width="7" height="7" rx="2" />
        <path d="M6 10v7h8" />
      </>
    ),
    check: <path d="M5 12l4 4L19 6" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    shield: (
      <>
        <path d="M12 2l9 4v6c0 5-9 10-9 10S3 17 3 12V6zM8 12l3 3 5-6" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.code}
    </svg>
  );
}

export function Header({
  workspace = "Candidate workspace",
  compact = false,
}: {
  workspace?: string;
  compact?: boolean;
}) {
  return (
    <header className={s.header}>
      <nav
        className={s.nav}
        style={compact ? { height: 56 } : undefined}
        aria-label="Main navigation"
      >
        <Link href="/" aria-label="OpenInterview home">
          <Logo />
        </Link>
        <span className={s.workspace}>{workspace}</span>
        <div className={s.navLinks}>
          <Link href="/roles">Roles</Link>
          <ThemeToggle />
          <AccountControl />
        </div>
      </nav>
    </header>
  );
}

export function Badge({
  children,
  tone = "",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return (
    <span
      className={`${s.badge} ${tone === "green" ? s.green : tone === "amber" ? s.amber : ""}`}
    >
      {children}
    </span>
  );
}

export function ExampleNote({ children }: { children: ReactNode }) {
  return (
    <div className={s.exampleNote}>
      <span className={s.dot} /> {children}
    </div>
  );
}

export function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className={s.pageTitle}>
      <span className={s.eyebrow}>{eyebrow}</span>
      <div className={s.titleRow}>
        <h1>{title}</h1>
        {action}
      </div>
      <p>{description}</p>
    </div>
  );
}
