"use client";

import { useState } from "react";
import fixture from "../../fixtures/synthetic/v1.json";
import { Badge } from "./ui";
import s from "./workspace.module.css";

// No live report pipeline exists yet. This drawer shows the shared synthetic
// fixture so reviewers can judge the layout; nothing here is real evidence.
const report = fixture.reports[0];
const corrected = fixture.turns.find((t) => t.id === "syn_corrected");

function ReportDrawer({ onClose, notify }: { onClose: () => void; notify: (message: string) => void }) {
  const [reviewed, setReviewed] = useState(false);
  const [note, setNote] = useState("");
  const [correction, setCorrection] = useState("");
  return (
    <section className={s.formPanel}>
      <div className={s.toolbar}>
        <div><span className={s.eyebrow}>SYNTHETIC REPORT · INPUT V{report.input_version}</span><h3>A conversation, with context.</h3></div>
        <button className={s.linkButton} onClick={onClose}>Close</button>
      </div>
      <Badge tone="amber">Unverified English summary</Badge>
      <p>{report.summary}</p>
      <div className={s.evidence}>
        <div className={s.row}><h4>Support experience</h4><Badge>Partial evidence</Badge></div>
        <p>Self-reported experience. A concrete example was not collected.</p>
        <h4>Original evidence (Vietnamese)</h4>
        <blockquote lang="vi">{corrected?.finalized_text}</blockquote>
        <small>syn_corrected · Finalized candidate correction</small>
      </div>
      <details className={s.disclosure}>
        <summary>Original transcript (Vietnamese)</summary>
        {fixture.turns.map((t) => (
          <div className={s.transcript} key={t.id}>
            <small>{t.speaker} · {t.id} · {t.delivery_status}</small>
            <p lang="vi">{t.finalized_text}</p>
          </div>
        ))}
      </details>
      <div className={s.formGrid}>
        <div><h4>Corrections</h4><p>syn_corrected replaces syn_answer. The original turn is preserved.</p></div>
        <div><h4>Missing & refused information</h4><p>Availability: refused. Education: not collected. Neither indicates low ability.</p></div>
        <div><h4>FAQ sources</h4><p>Weekend question: no confirmed source. Recruiter follow-up is pending.</p></div>
        <div><h4>CV provenance</h4><p>No CV attached. CV metadata is not interview evidence.</p></div>
      </div>
      <label>Correction request<textarea value={correction} onChange={(e) => setCorrection(e.target.value)} maxLength={2000} rows={2} placeholder="Describe a correction for recruiter follow-up" /></label>
      <button className={s.outlineButton} disabled={!correction.trim()} onClick={() => { setReviewed(false); notify("Correction noted on this page only. A real correction needs finalized turn references, a new input version and fresh human review."); }}>
        Preview correction request
      </button>
      <label>Human review note<textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} rows={2} placeholder="Record what you checked against the original evidence" /></label>
      <div className={s.formActions}>
        <button className={s.outlineButton} onClick={() => notify("Report retry is unavailable: no report job is connected. No new report was generated.")}>Check retry availability</button>
        <button className={s.primaryButton} disabled={!note.trim() || reviewed} onClick={() => { setReviewed(true); notify("Marked reviewed on this page only. No real approval was recorded."); }}>
          {reviewed ? "Reviewed (local)" : "Mark reviewed"}
        </button>
      </div>
    </section>
  );
}

export function ReportsTab({ notify }: { notify: (message: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <div className={s.toolbar}>
        <div><h2>Interview reports</h2><p>Evidence to inform your review, never an automated decision.</p></div>
      </div>
      <p className={s.small}>Preparation sessions produce no report. The row below is a synthetic example of the review layout.</p>
      <div className={s.tableWrap}>
        <table className={s.table}>
          <thead><tr><th>CANDIDATE</th><th>CAMPAIGN</th><th>REVIEW STATUS</th><th><span className={s.srOnly}>Actions</span></th></tr></thead>
          <tbody>
            <tr>
              <td><span className={s.tableName}>Synthetic candidate</span><small>{report.id} · Example</small></td>
              <td>Synthetic campaign</td>
              <td><Badge tone="amber">Needs human review</Badge></td>
              <td><button className={s.linkButton} aria-expanded={open} onClick={() => setOpen(!open)}>Review report ↗</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      {open && <ReportDrawer onClose={() => setOpen(false)} notify={notify} />}
    </>
  );
}
