import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import VoiceClient from './voice-client';

export const dynamic = 'force-dynamic';
export default async function LocalVoice() {
  const host = (await headers()).get('host') ?? '';
  if (process.env.NODE_ENV !== 'development' || !/^(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/.test(host)) notFound();
  return <VoiceClient />;
}
