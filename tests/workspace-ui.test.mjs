import { test } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { load } from "./render-ui.mjs";

const { HRScreen, AdminScreen } = load("app/components/workspaces.tsx");
const room = {
  id: "room-1", role_id: "frontend", campaign_name: "Web team", campaign_id: "camp-1",
  opens_at: "2026-11-12T02:00:00Z", closes_at: "2026-11-12T02:30:00Z", timezone: "Asia/Ho_Chi_Minh",
  contact: "r@example.com", ready: false, session_id: null, ended_at: null,
};

test("HR shows server campaigns, three tabs and labels drafts as local", () => {
  const html = renderToStaticMarkup(React.createElement(HRScreen, { rooms: [room, { ...room, id: "room-2" }] }));
  assert.equal((html.match(/role="tab"/g) || []).length, 3);
  assert.equal((html.match(/>Web team</g) || []).length, 1, "one campaign row per campaign_id");
  assert.match(html, /Locked · server/);
  assert.match(html, /New campaign/);
  assert.match(html, /not saved/);
});

test("Admin lists only active grants and never claims a sent invitation", () => {
  const grant = { id: "g1", account_id: "u1", permission: "hr", campaign_id: "camp-1", granted_by: "u0", created_at: "2026-11-01", confirmed_at: "2026-11-01", revoked_at: null };
  const data = {
    users: [{ id: "u1", name: "A", email: "a@example.com", role: "candidate" }],
    grants: [grant, { ...grant, id: "g2", campaign_id: "camp-2", revoked_at: "2026-11-02" }],
    checked_at: "2026-11-11T00:00:00Z", database: "reachable", jobs: "unknown",
  };
  const html = renderToStaticMarkup(React.createElement(AdminScreen, { data }));
  assert.match(html, /hr: camp-1/);
  assert.doesNotMatch(html, /hr: camp-2/);
  assert.match(html, /Revoked/);
  assert.match(html, /Invite HR/);
  assert.doesNotMatch(html, /invitation (was )?sent/i);
});
