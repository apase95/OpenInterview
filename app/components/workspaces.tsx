"use client";

import { useState } from "react";
import { careers, Room } from "./api";
import { CampaignRow, CampaignsTab } from "./hr-campaigns";
import { RoomsTab } from "./hr-rooms";
import { ReportsTab } from "./hr-report";
import { ExampleNote, Header, PageTitle } from "./ui";
import s from "./workspace.module.css";

export { AdminScreen } from "./admin-screen";

const TABS = ["Campaigns", "Rooms", "Reports"] as const;
type Tab = (typeof TABS)[number];

// Campaigns visible to this HR user, derived from rooms in confirmed scopes.
function serverCampaigns(rooms: Room[]): CampaignRow[] {
  const byId = new Map<string, CampaignRow>();
  for (const r of rooms)
    byId.set(r.campaign_id, {
      id: r.campaign_id,
      name: r.campaign_name,
      role: careers.find((c) => c[0] === r.role_id)?.[1] ?? r.role_id,
      status: "Locked · server",
      source: "server",
    });
  return [...byId.values()];
}

function TabList({ tab, counts, onSelect }: { tab: Tab; counts: Record<Tab, number>; onSelect: (t: Tab) => void }) {
  function key(event: React.KeyboardEvent, index: number) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? TABS.length - 1 : (index + (event.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length;
    onSelect(TABS[next]);
    document.getElementById(`tab-${TABS[next]}`)?.focus();
  }
  return (
    <div className={s.tabs} role="tablist" aria-label="Recruiter workspace">
      {TABS.map((t, i) => (
        <button key={t} id={`tab-${t}`} role="tab" aria-selected={tab === t} aria-controls="hr-panel" tabIndex={tab === t ? 0 : -1} className={tab === t ? s.activeTab : ""} onClick={() => onSelect(t)} onKeyDown={(e) => key(e, i)}>
          {t}<span>{counts[t]}</span>
        </button>
      ))}
    </div>
  );
}

export function HRScreen({ rooms }: { rooms: Room[] }) {
  const [tab, setTab] = useState<Tab>("Campaigns");
  const [notice, setNotice] = useState("");
  const [campaigns, setCampaigns] = useState(() => serverCampaigns(rooms));
  const select = (t: Tab) => { setTab(t); setNotice(""); };
  return (
    <div className={s.root}>
      <Header workspace="Recruiter workspace" />
      <main className={s.main}>
        <PageTitle eyebrow="RECRUITER WORKSPACE" title="Good conversations start here." description="Prepare your campaigns, organize rooms, and review the evidence." />
        <TabList tab={tab} counts={{ Campaigns: campaigns.length, Rooms: rooms.length, Reports: 1 }} onSelect={select} />
        {notice && <p className={s.notice} role="status">{notice}</p>}
        <section id="hr-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
          {tab === "Campaigns" && <CampaignsTab campaigns={campaigns} setCampaigns={setCampaigns} notify={setNotice} />}
          {tab === "Rooms" && <RoomsTab rooms={rooms} campaigns={campaigns} notify={setNotice} />}
          {tab === "Reports" && <ReportsTab notify={setNotice} />}
        </section>
        <ExampleNote>Server data: assigned campaigns and preparation rooms. Drafts, locks and reviews marked “local” stay in this tab and are not saved.</ExampleNote>
      </main>
    </div>
  );
}
