import { test } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { load } from "./render-ui.mjs";
const { default: Card, authError } = load("app/auth-ui/AuthCard.tsx");

test("one Google action preserves canonical invitation destinations", () => {
  for (const target of [
    "/roles",
    "/rooms/room-one",
    "/sessions/session-one/interview",
    "//evil.test",
    "/rooms/abc?next=evil",
  ]) {
    const html = renderToStaticMarkup(
      React.createElement(Card, { returnTo: target }),
    );
    const expected = target.includes("evil") ? "/" : target;
    assert.match(html, /Continue with Google/);
    assert.ok(html.includes("return_to=" + encodeURIComponent(expected)));
    assert.equal(
      (html.match(/href="\/api\/auth\/google\/start/g) || []).length,
      1,
    );
    assert.equal((html.match(/aria-label="Main navigation"/g) || []).length, 1);
    assert.doesNotMatch(html, /href="\/signup"|password|<input/);
    assert.match(html, /Account terms &amp; privacy/);
  }
});
test("query errors are fixed English copy", () => {
  assert.match(authError("cancel"), /cancelled/);
  assert.match(authError("state_invalid"), /expired/);
  assert.equal(authError("<script>private</script>"), authError("unknown"));
});
test("one server-owned origin proxies all browser APIs and the legacy callback", async () => {
  const { authBackend, default: config } = await import("../next.config.mjs");
  assert.equal(authBackend("http://127.0.0.1:8123"), "http://127.0.0.1:8123");
  for (const target of [
    "https://user:secret@api.internal",
    "file:///tmp/api",
    "https://api.internal/path",
    "https://api.internal?target=elsewhere",
  ])
    assert.throws(() => authBackend(target));
  const previous = process.env.API_BACKEND_URL;
  try {
    process.env.API_BACKEND_URL = "http://127.0.0.1:8123";
    assert.deepEqual(await config.rewrites(), [
      { source: "/api/auth/:path*", destination: "http://127.0.0.1:8123/auth/:path*" },
      { source: "/api/workspace/:path*", destination: "http://127.0.0.1:8123/workspace/:path*" },
      {
        source: "/auth/:path*",
        destination: "http://127.0.0.1:8123/auth/:path*",
      },
    ]);
  } finally {
    if (previous === undefined) delete process.env.API_BACKEND_URL;
    else process.env.API_BACKEND_URL = previous;
  }
});
test("server page guard rejects absent, expired and insufficient identities", async () => {
  const { proxy } = load("proxy.ts");
  const { NextRequest } = await import("next/server.js");
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response("{}", { status: 401 });
    let response = await proxy(
      new NextRequest("https://app.test/rooms/room-one"),
    );
    assert.equal(response.status, 307);
    assert.equal(
      new URL(response.headers.get("location")).searchParams.get("return_to"),
      "/rooms/room-one",
    );
    globalThis.fetch = async () =>
      Response.json({ user: { id: "candidate", grants: [] } });
    assert.equal(
      (await proxy(new NextRequest("https://app.test/admin"))).status,
      403,
    );
    assert.equal(
      (await proxy(new NextRequest("https://app.test/hr"))).status,
      403,
    );
    assert.equal(
      (await proxy(new NextRequest("https://app.test/roles"))).status,
      200,
    );
    globalThis.fetch = async () => {
      throw Error("PRIVATE");
    };
    response = await proxy(new NextRequest("https://app.test/roles"));
    assert.equal(response.status, 503);
    assert.doesNotMatch(await response.text(), /PRIVATE/);
  } finally {
    globalThis.fetch = previous;
  }
});
