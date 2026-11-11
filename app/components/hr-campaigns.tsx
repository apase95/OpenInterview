"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Badge, Icon } from "./ui";
import s from "./workspace.module.css";

// Server campaigns come from the HR scope. Drafts are local React state only:
// real approval/locking needs an authorized reviewer and server validation.
export type CampaignRow = {
  id: string;
  name: string;
  role: string;
  status: string;
  source: "server" | "draft";
  jd?: string;
  questions?: string;
  rubric?: string;
  faq?: string;
};

const ROLES = ["BA", "DevOps", "Fullstack", "Frontend", "Backend", "AI Engineer"];
const text = (form: FormData, name: string) => String(form.get(name) || "").trim();

function CampaignForm({ onSave, onCancel }: { onSave: (c: CampaignRow) => void; onCancel: () => void }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSave({
      id: `draft-${crypto.randomUUID()}`,
      name: text(data, "name"),
      role: text(data, "role"),
      status: "Draft",
      source: "draft",
      jd: text(data, "jd"),
      questions: text(data, "questions"),
      rubric: text(data, "rubric"),
      faq: text(data, "faq"),
    });
  }
  return (
    <form className={s.formPanel} onSubmit={submit}>
      <div className={s.sectionTitle}>
        <span className={s.iconBox}><Icon name="layers" /></span>
        <h3>New campaign <Badge>Local draft</Badge></h3>
      </div>
      <div className={s.formGrid}>
        <label>Campaign name<input name="name" required maxLength={100} placeholder="e.g. Platform team" /></label>
        <label>Role<select name="role">{ROLES.map((r) => <option key={r}>{r}</option>)}</select></label>
      </div>
      <label>Job description<textarea name="jd" required maxLength={5000} rows={3} placeholder="Describe the role and its responsibilities" /></label>
      <div className={s.formGrid}>
        <label>Common questions<textarea name="questions" required maxLength={3000} rows={3} placeholder="Questions shared across interviews" /></label>
        <label>Review rubric<textarea name="rubric" required maxLength={3000} rows={3} placeholder="Evidence a reviewer should look for" /></label>
      </div>
      <label>FAQ sources & validity<textarea name="faq" required maxLength={3000} rows={2} placeholder="Source, version, validity dates and approval owner" /></label>
      <div className={s.formActions}>
        <button className={s.outlineButton} type="button" onClick={onCancel}>Cancel</button>
        <button className={s.primaryButton} type="submit">Save local draft</button>
      </div>
    </form>
  );
}

function CampaignDetail({ campaign, onLock, onClose }: { campaign: CampaignRow; onLock: () => void; onClose: () => void }) {
  const sections = [
    ["Job description", campaign.jd],
    ["Common questions", campaign.questions],
    ["Review rubric", campaign.rubric],
    ["FAQ sources & validity", campaign.faq],
  ];
  return (
    <section className={s.formPanel}>
      <div className={s.toolbar}>
        <h3>{campaign.name} <Badge>{campaign.status}</Badge></h3>
        <button className={s.linkButton} onClick={onClose}>Close</button>
      </div>
      {campaign.source === "server" ? (
        <p className={s.small}>Versioned hiring content (JD, questions, rubric, FAQ) is not connected yet. This campaign is visible because of your confirmed HR scope.</p>
      ) : (
        <div className={s.formGrid}>
          {sections.map(([label, content]) => (
            <div key={label}><h4>{label}</h4><p className={s.preserve}>{content}</p></div>
          ))}
        </div>
      )}
      {campaign.status === "Draft" ? (
        <button className={s.primaryButton} onClick={onLock}>Preview approval & lock v1</button>
      ) : (
        <p className={s.small}>Locked versions cannot be edited. Changes require a new version.</p>
      )}
    </section>
  );
}

export function CampaignsTab({
  campaigns,
  setCampaigns,
  notify,
}: {
  campaigns: CampaignRow[];
  setCampaigns: (next: CampaignRow[]) => void;
  notify: (message: string) => void;
}) {
  const [form, setForm] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const campaign = campaigns.find((c) => c.id === selected);
  return (
    <>
      <div className={s.toolbar}>
        <div><h2>Your campaigns</h2><p>A shared foundation for every conversation.</p></div>
        <button className={s.primaryButton} aria-expanded={form} onClick={() => { setForm(!form); setSelected(null); }}>
          <Icon name="plus" size={17} />New campaign
        </button>
      </div>
      {form && (
        <CampaignForm
          onCancel={() => setForm(false)}
          onSave={(c) => {
            setCampaigns([...campaigns, c]);
            setForm(false);
            notify("Local draft created. No campaign was saved to the server.");
          }}
        />
      )}
      <div className={s.tableWrap}>
        <table className={s.table}>
          <thead><tr><th>CAMPAIGN</th><th>ROLE</th><th>VERSION & STATUS</th><th><span className={s.srOnly}>Actions</span></th></tr></thead>
          <tbody>
            {campaigns.map((c) => (
              <tr key={c.id}>
                <td><span className={s.tableName}>{c.name}</span><small>{c.source === "server" ? c.id : "Local draft"}</small></td>
                <td>{c.role}</td>
                <td><Badge tone={c.status === "Draft" ? "amber" : ""}>{c.status}</Badge></td>
                <td>
                  <button className={s.linkButton} aria-expanded={selected === c.id} onClick={() => setSelected(selected === c.id ? null : c.id)}>
                    View details ↗
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!campaigns.length && <p className="p-6">No campaigns in your assigned scopes.</p>}
      </div>
      {campaign && (
        <CampaignDetail
          campaign={campaign}
          onClose={() => setSelected(null)}
          onLock={() => {
            setCampaigns(campaigns.map((c) => (c.id === campaign.id ? { ...c, status: "Locked · v1 (local)" } : c)));
            notify("Version locked in this page only. Real approval requires an authorized reviewer and server validation.");
          }}
        />
      )}
    </>
  );
}
