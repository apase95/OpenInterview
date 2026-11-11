"use client";

import { useEffect } from "react";

const key = "openinterview-theme";

export function ThemeSync() {
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const sync = () => {
      let saved: string | null = null;
      try {
        saved = localStorage.getItem(key);
      } catch {
        /* Use the system theme when storage is unavailable. */
      }
      document.documentElement.dataset.theme =
        saved === "light" || saved === "dark"
          ? saved
          : media.matches
            ? "light"
            : "dark";
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === key || event.key === null) sync();
    };
    media.addEventListener("change", sync);
    window.addEventListener("storage", onStorage);
    return () => {
      media.removeEventListener("change", sync);
      window.removeEventListener("storage", onStorage);
    };
  }, []);
  return null;
}

export default function ThemeToggle() {
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label="Toggle color theme"
      onClick={() => {
        const next =
          document.documentElement.dataset.theme === "light" ? "dark" : "light";
        document.documentElement.dataset.theme = next;
        try {
          localStorage.setItem(key, next);
        } catch {
          /* Switching still works for this page. */
        }
      }}
    >
      <span className="theme-to-light">
        <svg
          width="17"
          height="17"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5" />
        </svg>
        <span>Light mode</span>
      </span>
      <span className="theme-to-dark">
        <svg
          width="17"
          height="17"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M20.8 13.1A9 9 0 0110.9 3.2 9 9 0 1020.8 13.1z" />
        </svg>
        <span>Dark mode</span>
      </span>
    </button>
  );
}
