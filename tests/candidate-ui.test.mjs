import { test } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { load } from "./render-ui.mjs";
const { RolesScreen, InterviewScreen } = load("app/components/candidate.tsx");
test("Roles renders six professions and no code-entry or premature microphone action", () => {
  const html = renderToStaticMarkup(React.createElement(RolesScreen));
  assert.equal((html.match(/<article/g) || []).length, 6);
  assert.doesNotMatch(
    html,
    /room-code|Explore demo|Check microphone|No room assigned/,
  );
  assert.match(html, /Loading assigned rooms/);
  assert.equal((html.match(/aria-label="Main navigation"/g) || []).length, 1);
});
test("Interview has a stage, exactly three actions and no navigation", () => {
  const html = renderToStaticMarkup(
    React.createElement(InterviewScreen, { id: "session-one" }),
  );
  assert.equal((html.match(/<button/g) || []).length, 3);
  for (const text of ["Mute microphone", "Mute speaker", "End interview"])
    assert.ok(html.includes(text));
  assert.doesNotMatch(html, /<nav|<header|Finish demo/);
});
test("Home restores specified copy and both calls to action reach assigned rooms", () => {
  const html = renderToStaticMarkup(
    React.createElement(load("app/page.tsx").default),
  );
  assert.match(
    html,
    /AI leads a short interview. Recruiters review the evidence./,
  );
  assert.doesNotMatch(html, /#invitation/);
  assert.equal((html.match(/href="\/roles"/g) || []).length, 3);
});
