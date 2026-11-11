"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Session } from "./api";
import { Icon } from "./ui";
import { clearPendingEnd, markPendingEnd, pendingEnd } from "./pending-end";
import s from "./workspace.module.css";
import { errorText } from "./candidate-common";

export function InterviewScreen({ id }: { id: string }) {
  const router = useRouter();
  const [mic, setMic] = useState(false);
  const [speaker, setSpeaker] = useState(false);
  const [status, setStatus] = useState("Checking session…");
  const ended = useRef(false);
  useEffect(() => {
    let active = true;
    if (pendingEnd() === id) {
      ended.current = true;
      void api(`/sessions/${encodeURIComponent(id)}/end`, {})
        .then(() => {
          clearPendingEnd(id);
          router.replace("/roles?ended=1");
        })
        .catch(() => router.replace("/roles?ended=1"));
      return () => {
        active = false;
      };
    }
    const check = () =>
      api<Session>(`/sessions/${encodeURIComponent(id)}`)
        .then((ses) => {
          if (active && !ended.current) {
            if (ses.ended_at) router.replace("/roles?ended=1");
            else setStatus("Preparation only · No audio connected");
          }
        })
        .catch((e) => {
          if (active && !ended.current) setStatus(errorText(e));
        });
    void check();
    const timer = window.setInterval(() => void check(), 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id, router]);
  function end() {
    if (ended.current) return;
    ended.current = true;
    setStatus("Ending…");
    markPendingEnd(id);
    // No capture/playback exists in preparation mode. The server end is idempotent.
    const attempt = async () => {
      for (let n = 0; n < 3; n++) {
        try {
          await api(`/sessions/${encodeURIComponent(id)}/end`, {}, true);
          clearPendingEnd(id);
          return true;
        } catch {
          if (n < 2) await new Promise((r) => setTimeout(r, 300 * (n + 1)));
        }
      }
      return false;
    };
    // Leave immediately; the sessionStorage marker lets Roles retry if needed.
    void attempt();
    router.replace("/roles?ended=1");
  }
  return (
    <main className={s.interview}>
      <div className={s.stage}>
        <span className={s.stageLabel}>VOICE INTERVIEW</span>
        <div className={s.orbit}>
          <img
            src="/images/robot.svg"
            width="300"
            height="300"
            alt="Purple AI interviewer"
          />
        </div>
        <div className={s.stageStatus} role="status">
          <span className={s.dot} />
          {status}
        </div>
      </div>
      <div
        className={s.interviewControls}
        role="group"
        aria-label="Interview controls"
      >
        <button onClick={() => setMic(!mic)}>
          <span className={mic ? s.controlMuted : s.controlIcon}>
            <Icon name="mic" />
            {mic && <i />}
          </span>
          {mic ? "Unmute microphone" : "Mute microphone"}
        </button>
        <button onClick={() => setSpeaker(!speaker)}>
          <span className={speaker ? s.controlMuted : s.controlIcon}>
            <Icon name="speaker" />
            {speaker && <i />}
          </span>
          {speaker ? "Unmute speaker" : "Mute speaker"}
        </button>
        <button className={s.endControl} onClick={end}>
          <span className={s.controlIcon}>
            <Icon name="end" />
          </span>
          End interview
        </button>
      </div>
    </main>
  );
}
