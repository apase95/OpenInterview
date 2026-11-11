"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, careers, Room, schedule } from "./api";
import { Badge, Header, Icon, PageTitle } from "./ui";
import { clearPendingEnd, pendingEnd } from "./pending-end";
import s from "./workspace.module.css";
import { ErrorNotice, errorText } from "./candidate-common";

export function RolesScreen() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [ended, setEnded] = useState(false);
  const [endPending, setEndPending] = useState(false);
  useEffect(() => {
    let active = true;
    setEnded(new URLSearchParams(location.search).get("ended") === "1");
    // Only this tab's own marker may trigger End; a URL must never end a session.
    const pending = pendingEnd();
    setEndPending(!!pending);
    if (pending)
      void api(`/sessions/${pending}/end`, {})
        .then(() => {
          clearPendingEnd(pending);
          if (active) setEndPending(false);
        })
        .catch(() => {});
    api<Room[]>("/rooms")
      .then((value) => {
        if (active) setRooms(value);
      })
      .catch((e) => {
        if (active) setError(errorText(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <div className={s.root}>
      <Header />
      <main className={s.main}>
        <PageTitle
          eyebrow="YOUR ROOMS"
          title="Find your conversation."
          description="Your recruiter assigns a room and time. Choose your assigned room to prepare."
        />
        {ended && (
          <p className={s.success} role="status">
            Interview ended locally.{" "}
            {endPending
              ? "Server confirmation is pending. Refresh to retry."
              : "Preparation only; no interview audio was collected."}
          </p>
        )}
        <ErrorNotice error={error} />
        {loading && <p role="status">Loading assigned rooms…</p>}
        <div className={s.roleGrid}>
          {careers.map(([id, name, description, icon]) => (
            <article
              key={id}
              className={`${s.roleCard} ${rooms.some((r) => r.role_id === id) ? s.assigned : ""}`}
            >
              <div className={s.roleHeading}>
                <span className={s.iconBox}>
                  <Icon name={icon} />
                </span>
                <div>
                  <h2>{name}</h2>
                  <p>{description}</p>
                </div>
              </div>
              <div className={s.roomRow}>
                {rooms
                  .filter((r) => r.role_id === id)
                  .map((r) => (
                    <div key={r.id}>
                      <div className={s.row}>
                        <strong>{r.campaign_name}</strong>
                        <Badge>
                          {r.ended_at
                            ? "Ended"
                            : r.ready
                              ? "Available"
                              : "Scheduled"}
                        </Badge>
                      </div>
                      <p>{schedule(r)}</p>
                      <Link className={s.textLink} href={`/rooms/${r.id}`}>
                        Open room <span>↗</span>
                      </Link>
                    </div>
                  ))}
                {!loading && !error && !rooms.some((r) => r.role_id === id) && (
                  <p>No room assigned</p>
                )}
              </div>
            </article>
          ))}
        </div>
        <p className={s.footnote}>
          Expecting an invitation? Sign in with the account your recruiter
          invited. Rooms are assigned to your verified identity.
        </p>
      </main>
    </div>
  );
}
