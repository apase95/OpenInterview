"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, careers, Room, Session, schedule } from "./api";
import { Badge, Header, Icon, PageTitle } from "./ui";
import s from "./workspace.module.css";
import { ErrorNotice, errorText } from "./candidate-common";

export function JoinScreen({ id }: { id: string }) {
  const router = useRouter();
  const [room, setRoom] = useState<Room | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ack, setAck] = useState(false);
  const [mic, setMic] = useState("Not checked");
  const [speaker, setSpeaker] = useState(false);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);
  const generation = useRef(0);
  const audio = useRef<AudioContext | null>(null);
  const mounted = useRef(true);
  const stop = () => {
    generation.current++;
    if (audio.current && audio.current.state !== "closed")
      void audio.current.close().catch(() => {});
    audio.current = null;
  };
  useEffect(() => {
    mounted.current = true;
    api<Room>(`/rooms/${encodeURIComponent(id)}`)
      .then((value) => {
        if (mounted.current) setRoom(value);
      })
      .catch((e) => {
        if (mounted.current) setError(errorText(e));
      })
      .finally(() => {
        if (mounted.current) setLoading(false);
      });
    const leave = () => stop();
    window.addEventListener("pagehide", leave);
    return () => {
      mounted.current = false;
      stop();
      window.removeEventListener("pagehide", leave);
    };
  }, [id]);
  async function checkMic() {
    if (!ack || checking) return;
    const current = ++generation.current;
    setChecking(true);
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      if (mounted.current && current === generation.current)
        setMic("Microphone available");
    } catch {
      if (mounted.current && current === generation.current)
        setMic(
          "Microphone unavailable. Check browser permissions and your device.",
        );
    } finally {
      if (mounted.current) setChecking(false);
    }
  }
  async function testSpeaker() {
    if (!ack) return;
    stop();
    try {
      const context = new AudioContext();
      audio.current = context;
      const current = generation.current;
      await context.resume();
      if (!mounted.current || current !== generation.current) return;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = 523;
      gain.gain.setValueAtTime(0, context.currentTime);
      gain.gain.linearRampToValueAtTime(0.1, context.currentTime + 0.03);
      gain.gain.linearRampToValueAtTime(0, context.currentTime + 0.6);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.65);
      oscillator.onended = () => {
        if (context.state !== "closed") void context.close().catch(() => {});
      };
      setSpeaker(true);
    } catch {
      if (mounted.current)
        setError("Speaker unavailable. Check your audio output and try again.");
    }
  }
  async function join() {
    if (!ack || busy) return;
    setBusy(true);
    setError("");
    stop();
    try {
      const session = await api<Session>(
        `/rooms/${encodeURIComponent(id)}/sessions`,
        { acknowledged: true },
      );
      router.push(
        session.ended_at
          ? "/roles?ended=1"
          : `/sessions/${session.id}/interview`,
      );
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  }
  return (
    <div className={s.root}>
      <Header />
      <main className={s.main}>
        <Link href="/roles" className={s.backLink}>
          ← Your rooms
        </Link>
        <PageTitle
          eyebrow="JOIN ROOM"
          title="A moment to get ready."
          description="Review the details, then check your audio. You decide when to begin."
        />
        <ErrorNotice error={error} />
        {loading && <p role="status">Checking your assigned room…</p>}
        {room && (
          <div className={s.joinGrid}>
            <aside className={s.panel}>
              <span className={s.iconBox}>
                <Icon name="window" />
              </span>
              <h2>{careers.find((r) => r[0] === room.role_id)?.[1]}</h2>
              <p>{room.campaign_name}</p>
              <div className={s.detailItem}>
                <Icon name="clock" />
                <div>
                  <strong>{schedule(room)}</strong>
                  <p>Interview language: Vietnamese</p>
                </div>
              </div>
              <div className={s.waiting}>
                <Badge>
                  {room.ended_at
                    ? "Ended"
                    : room.ready
                      ? "Available for preparation"
                      : "Not available yet"}
                </Badge>
                <p>Availability is rechecked by the server when joining.</p>
              </div>
              <a
                className={s.textLink}
                href={`mailto:${encodeURIComponent(room.contact)}`}
              >
                Contact recruiter ↗
              </a>
            </aside>
            <div className={s.stack}>
              <section className={s.panel}>
                <div className={s.sectionTitle}>
                  <span className={s.step}>01</span>
                  <h2>Your conversation, your choice</h2>
                </div>
                <Badge>Preparation only</Badge>
                <p>
                  Live AI interviews are not enabled. No interview audio,
                  finalized transcript or report is collected in this
                  preparation session.
                </p>
                <details className={s.disclosure} open>
                  <summary>Data, privacy & your choices</summary>
                  <p>
                    We store your account assignment, preparation
                    acknowledgement and session start/end metadata. Device
                    testing is local: microphone tracks stop immediately after
                    the permission check. Audio is not recorded or uploaded. A
                    test tone does not prove that you heard it.
                  </p>
                  <p>
                    An approved interview notice, policy version, retention by
                    data type, viewers and verified correction/deletion contact
                    are still required for live recruitment interviews. This
                    acknowledgement is not legal interview consent. Contact your
                    recruiter before proceeding if your assignment is incorrect.
                  </p>
                </details>
                <label className={s.checkbox}>
                  <input
                    type="checkbox"
                    checked={ack}
                    disabled={busy}
                    onChange={(e) => {
                      setAck(e.target.checked);
                      if (!e.target.checked) {
                        stop();
                        setMic("Not checked");
                        setSpeaker(false);
                      }
                    }}
                  />
                  <span>
                    I understand this preparation-only notice and agree to local
                    device testing and storing preparation acknowledgement.
                  </span>
                </label>
                <Link className={s.subtleLink} href="/roles">
                  Decline and return to rooms
                </Link>
              </section>
              <section className={s.panel}>
                <div className={s.sectionTitle}>
                  <span className={s.step}>02</span>
                  <h2>Make yourself heard</h2>
                </div>
                <div className={s.deviceGrid}>
                  <div className={s.device}>
                    <Icon name="mic" />
                    <h3>Microphone</h3>
                    <p role="status">
                      {checking ? "Waiting for browser permission…" : mic}
                    </p>
                    <button
                      className={s.outlineButton}
                      disabled={!ack || checking || busy}
                      onClick={() => void checkMic()}
                    >
                      Check microphone
                    </button>
                  </div>
                  <div className={s.device}>
                    <Icon name="speaker" />
                    <h3>Speaker</h3>
                    <p role="status">
                      {speaker
                        ? "Test tone played. Did you hear it?"
                        : "Play a short test tone"}
                    </p>
                    <button
                      className={s.outlineButton}
                      disabled={!ack || checking || busy}
                      onClick={() => void testSpeaker()}
                    >
                      Test speaker
                    </button>
                  </div>
                </div>
                <div className={s.joinFooter}>
                  <p>
                    Preparation interface only.
                    <br />
                    No live AI or media connection.
                  </p>
                  <button
                    className={s.primaryButton}
                    disabled={
                      !ack || busy || checking || !room.ready || !!room.ended_at
                    }
                    onClick={() => void join()}
                  >
                    {busy ? "Opening…" : "Join interview"}
                    <Icon name="arrow" size={16} />
                  </button>
                </div>
                <p className={s.small}>
                  You can skip local device testing. No microphone is used by
                  the preparation session.
                </p>
              </section>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
