import type { Metadata } from "next";
import "./globals.css";
import { ThemeSync } from "./components/theme-toggle";

export const metadata: Metadata = {
  title: "OpenInterview",
  icons: { icon: "/images/logo.svg" },
  description: "Voice interviews in Vietnamese, with human review.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){var t;try{t=localStorage.getItem('openinterview-theme')}catch(e){}document.documentElement.dataset.theme=t==='light'||t==='dark'?t:window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'})()`,
          }}
        />
      </head>
      <body>
        <ThemeSync />
        {children}
      </body>
    </html>
  );
}
