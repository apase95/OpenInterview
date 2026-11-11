"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Badge, ExampleNote, Header, Icon, PageTitle } from "./ui";
import s from "./workspace.module.css";

type Grant = {
  id: string;
  account_id: string;
  permission: string;
  campaign_id: string | null;
  granted_by: string;
  created_at: string;
  confirmed_at: string | null;
  revoked_at: string | null;
};
export type AdminData = {
  users: { id: string; name: string | null; email: string; role: string }[];
  grants: Grant[];
  checked_at: string;
  database: string;
  jobs: string;
};

const active = (g: Grant) => g.confirmed_at && !g.revoked_at;
const grantStatus = (g: Grant) => (g.revoked_at ? "Revoked" : g.confirmed_at ? "Confirmed" : "Awaiting recipient confirmation");
const scope = (g: Grant) => g.campaign_id || "administration";

function InviteForm({ scopes, onSave, onCancel }: { scopes: string[]; onSave: (d: { email: string; scope: string }) => void; onCancel: () => void }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSave({ email: String(data.get("email") || "").trim(), scope: String(data.get("scope") || "") });
  }
  return (
    <form className={s.formPanel} onSubmit={submit}>
      <h3>Prepare an HR invitation <Badge>Local draft</Badge></h3>
      <div className={s.formGrid}>
        <label>Recipient email<input type="email" name="email" required maxLength={254} placeholder="recruiter@example.com" /></label>
        <label>Campaign scope<select name="scope" required>{scopes.map((c) => <option key={c}>{c}</option>)}</select></label>
      </div>
      <p className={s.small}>Real grants require backend authorization, recipient confirmation and an audit record.</p>
      <div className={s.formActions}>
        <button type="button" className={s.outlineButton} onClick={onCancel}>Cancel</button>
        <button className={s.primaryButton} disabled={!scopes.length}>Prepare invitation</button>
      </div>
    </form>
  );
}

function HealthCards({ data }: { data: AdminData }) {
  const cards = [
    ["Application API", "reachable", "Served this page.", "layers"],
    ["Database", data.database, "Authenticated query succeeded.", "database"],
    ["Report jobs", data.jobs, "No worker probe connected.", "clock"],
  ];
  return (
    <section className={s.healthSection}>
      <div className={s.toolbar}><div><h2>Service & job health</h2><p>Checked: {data.checked_at}</p></div></div>
      <div className={s.healthGrid}>
        {cards.map(([title, state, desc, icon]) => (
          <article key={title} className={s.healthCard}>
            <div className={s.row}><span className={s.iconBox}><Icon name={icon} /></span><Badge tone={state === "reachable" ? "green" : ""}>{state}</Badge></div>
            <h3>{title}</h3>
            <p>{desc}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export function AdminScreen({ data }: { data: AdminData }) {
  const [invite, setInvite] = useState(false);
  const [notice, setNotice] = useState("");
  const [draft, setDraft] = useState<{ email: string; scope: string } | null>(null);
  const scopes = [...new Set(data.grants.filter((g) => g.campaign_id).map((g) => g.campaign_id as string))];
  return (
    <div className={s.root}>
      <Header workspace="Admin workspace" />
      <main className={s.main}>
        <PageTitle eyebrow="ADMINISTRATION" title="The right access. Clearly defined." description="Verified accounts, confirmed grants and service metadata." />
        <div className={s.toolbar}>
          <div><h2>People & permissions</h2><p>HR grants are scoped to exact campaigns.</p></div>
          <button className={s.primaryButton} aria-expanded={invite} onClick={() => setInvite(!invite)}><Icon name="plus" size={17} />Invite HR</button>
        </div>
        {notice && <p className={s.notice} role="status">{notice}</p>}
        {invite && (
          <InviteForm
            scopes={scopes}
            onCancel={() => setInvite(false)}
            onSave={(d) => { setDraft(d); setInvite(false); setNotice("Invitation draft prepared on this page only. No email was sent and no permission was granted."); }}
          />
        )}
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead><tr><th>USER</th><th>ACCESS</th><th>SCOPE</th></tr></thead>
            <tbody>
              {data.users.map((user) => (
                <tr key={user.id}>
                  <td><span className={s.tableName}>{user.name || user.email}</span><small>{user.email}</small></td>
                  <td>{user.role}</td>
                  <td>{data.grants.filter((g) => g.account_id === user.id && active(g)).map((g) => `${g.permission}: ${scope(g)}`).join(", ") || "Assigned rooms only"}</td>
                </tr>
              ))}
              {draft && (
                <tr><td><span className={s.tableName}>{draft.email}</span><small>Invitation draft</small></td><td>HR requested</td><td>{draft.scope} <Badge tone="amber">Not sent</Badge></td></tr>
              )}
            </tbody>
          </table>
        </div>
        <p className={s.footnote}>Admin does not grant transcript, report or CV access.</p>
        <HealthCards data={data} />
        <details className={`${s.panel} ${s.audit}`}>
          <summary>Grant audit metadata <span>{data.grants.length} records</span></summary>
          {data.grants.map((g) => (
            <dl className={s.auditGrid} key={g.id}>
              <div><dt>Grant</dt><dd>{g.permission} · {scope(g)}</dd></div>
              <div><dt>Granted by</dt><dd>{g.granted_by}</dd></div>
              <div><dt>Created</dt><dd>{g.created_at}</dd></div>
              <div><dt>Status</dt><dd>{grantStatus(g)}</dd></div>
            </dl>
          ))}
          {!data.grants.length && <p>No grant records.</p>}
        </details>
        <ExampleNote>Drafts on this page stay in your browser tab. Grant changes need an authorized provisioning process.</ExampleNote>
      </main>
    </div>
  );
}
