// CSRF fetch-wrapper coverage for static/app.js (#231). The wrapper auto-adds
// the X-CSRFToken header to same-origin state-changing fetches; a regression
// here silently breaks every POST or leaks the token cross-origin, so it's the
// highest-value JS unit in the file.
import test from "node:test";
import assert from "node:assert/strict";

import { loadApp, recordingFetch } from "./helpers.mjs";

const META = '<meta name="csrf-token" content="tok-123">';
const armed = (body = "") =>
  `<!doctype html><html><head>${META}</head><body>${body}</body></html>`;

test("same-origin POST gets the X-CSRFToken header", async () => {
  const f = recordingFetch();
  const w = loadApp({ html: armed(), fetchStub: f });
  await w.fetch("/api/save", { method: "POST" });
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].init.headers.get("X-CSRFToken"), "tok-123");
});

test("method matching is case-insensitive (lowercase post)", async () => {
  const f = recordingFetch();
  const w = loadApp({ html: armed(), fetchStub: f });
  await w.fetch("/api/save", { method: "post" });
  assert.equal(f.calls[0].init.headers.get("X-CSRFToken"), "tok-123");
});

test("PUT/PATCH/DELETE are also tokenized", async () => {
  for (const method of ["PUT", "PATCH", "DELETE"]) {
    const f = recordingFetch();
    const w = loadApp({ html: armed(), fetchStub: f });
    await w.fetch("/api/x", { method });
    assert.equal(
      f.calls[0].init.headers.get("X-CSRFToken"),
      "tok-123",
      `expected token on ${method}`,
    );
  }
});

test("GET requests are left untouched", async () => {
  const f = recordingFetch();
  const w = loadApp({ html: armed(), fetchStub: f });
  await w.fetch("/api/read");
  // No headers object is attached for the safe-method passthrough.
  const h = f.calls[0].init.headers;
  assert.ok(!h || !h.get || !h.get("X-CSRFToken"));
});

test("cross-origin POST does NOT leak the token", async () => {
  const f = recordingFetch();
  const w = loadApp({ html: armed(), fetchStub: f });
  await w.fetch("https://third-party.test/collect", { method: "POST" });
  const h = f.calls[0].init.headers;
  assert.ok(!h || !h.get || !h.get("X-CSRFToken"));
});

test("an explicit X-CSRFToken header is preserved, not overwritten", async () => {
  const f = recordingFetch();
  const w = loadApp({ html: armed(), fetchStub: f });
  await w.fetch("/api/x", {
    method: "POST",
    headers: { "X-CSRFToken": "caller-set" },
  });
  assert.equal(f.calls[0].init.headers.get("X-CSRFToken"), "caller-set");
});

test("with no csrf meta tag the wrapper is a no-op (fetch unwrapped)", async () => {
  const f = recordingFetch();
  const w = loadApp({
    html: "<!doctype html><html><head></head><body></body></html>",
    fetchStub: f,
  });
  // Wrapper bails before replacing window.fetch, so it's still our stub.
  assert.equal(w.fetch, f);
  await w.fetch("/api/x", { method: "POST" });
  const h = f.calls[0].init.headers;
  assert.ok(!h || !h.get || !h.get("X-CSRFToken"));
});
