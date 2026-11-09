import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'OpenInterview',
  icons: { icon: '/images/logo.svg' },
  description: 'Voice interviews in Vietnamese, with human review.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
