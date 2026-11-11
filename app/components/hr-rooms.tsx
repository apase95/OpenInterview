"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Room, schedule } from "./api";
import type { CampaignRow } from "./hr-campaigns";
import { Badge, Icon } from "./ui";
import s from "./workspace.module.css";

type ServerRoom = Room & { revoked_at?: string | null };
type DraftRoom = { id: string; name: string; email: string; campaign: string; schedule: string };

const text = (form: FormData, name: string) => String(form.get(name) || "").trim();

function RoomForm({ campaigns, onSave, onCancel }: { campaigns: CampaignRow[]; onSave: (r: DraftRoom) => void; onCancel: () => void }) {
  const locked = campaigns.filter((c) => c.status.startsWith("Locked"));
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSave({
      id: `draft-${crypto.randomUUID().slice(0, 8)}`,
      name: text(data, "candidate"),
      email: text(data, "email"),
      campaign: text(data, "campaign"),
      schedule: `${text(data, "schedule").replace("T", " ")} · ${text(data, "timezone")}`,
    });
  }
  return (
    <form className={s.formPanel} onSubmit={submit}>
      <div className={s.sectionTitle}>
        <span className={s.iconBox}><Icon name="window" /></span>
        <h3>Create room <Badge>Local draft</Badge></h3>
      </div>
      <div className={s.formGrid}>
        <label>Candidate name<input name="candidate" required maxLength={100} placeholder="Full name" /></label>
        <label>Invited email<input type="email" name="email" required maxLength={254} placeholder="candidate@example.com" /></label>
        <label>
          Locked campaign
          <select name="campaign" required>
            {locked.map((c) => <option key={c.id} value={c.name}>{c.name} · {c.role} · {c.status}</option>)}
          </select>
        </label>
        <label>Start time<input type="datetime-local" name="schedule" required /></label>
        <label>Timezone<select name="timezone"><option>Asia/Ho_Chi_Minh</option><option>UTC</option></select></label>
        <label>Recruiter contact<input type="email" name="contact" required placeholder="recruiter@example.com" /></label>
      </div>
      {!locked.length && <p className={s.small}>Lock a campaign version before creating a room.</p>}
      <p className={s.small}>The invited email must match the verified account. This draft does not bind an identity.</p>
      <div className={s.attachment}>
        <Icon name="shield" />
        <div>
          <strong>No CV attached</strong>
          <p>Optional. Upload stays unavailable until disclosure authorization, private storage and security scanning are connected.</p>
        </div>
      </div>
      <div className={s.formActions}>
        <button className={s.outlineButton} type="button" onClick={onCancel}>Cancel</button>
        <button className={s.primaryButton} type="submit" disabled={!locked.length}>Save local draft</button>
      </div>
    </form>
  );
}

export function RoomsTab({ rooms, campaigns, notify }: { rooms: ServerRoom[]; campaigns: CampaignRow[]; notify: (message: string) => void }) {
  const [form, setForm] = useState(false);
  const [drafts, setDrafts] = useState<DraftRoom[]>([]);
  return (
    <>
      <div className={s.toolbar}>
        <div><h2>Interview rooms</h2><p>One candidate. One room. One locked campaign.</p></div>
        <button className={s.primaryButton} aria-expanded={form} onClick={() => setForm(!form)}>
          <Icon name="plus" size={17} />Create room
        </button>
      </div>
      {form && (
        <RoomForm
          campaigns={campaigns}
          onCancel={() => setForm(false)}
          onSave={(r) => {
            setDrafts([...drafts, r]);
            setForm(false);
            notify("Local room draft created with no CV attached. No invitation was sent.");
          }}
        />
      )}
      <div className={s.tableWrap}>
        <table className={s.table}>
          <thead><tr><th>CANDIDATE / ROOM</th><th>CAMPAIGN</th><th>SCHEDULE</th><th>STATUS</th><th><span className={s.srOnly}>Actions</span></th></tr></thead>
          <tbody>
            {rooms.map((r) => (
              <tr key={r.id}>
                <td><span className={s.tableName}>{r.id}</span><small>Assigned account</small></td>
                <td>{r.campaign_name}<small>No CV attached</small></td>
                <td>{schedule(r)}</td>
                <td><Badge>{r.revoked_at ? "Revoked" : "Preparation only"}</Badge></td>
                <td />
              </tr>
            ))}
            {drafts.map((r) => (
              <tr key={r.id}>
                <td><span className={s.tableName}>{r.name}</span><small>{r.email} · Local draft</small></td>
                <td>{r.campaign}<small>No CV attached</small></td>
                <td>{r.schedule}</td>
                <td><Badge tone="amber">Draft</Badge></td>
                <td>
                  <button className={s.linkButton} onClick={() => notify("Invitation not published. Verified identity, approved campaign, schedule and server authorization are required. No email was sent.")}>
                    Publish invitation ↗
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rooms.length && !drafts.length && <p className="p-6">No preparation rooms in your assigned scopes.</p>}
      </div>
    </>
  );
}
