// Test harness for static/app.js (#231). app.js is a set of browser IIFEs
// that run on load against the global `document` / `window` — it exports
// nothing — so we exercise it by loading the real source into a jsdom window
// and asserting on observable behaviour (wrapped fetch, dispatched events,
// DOM mutations).
//
// jsdom doesn't implement fetch / Headers / FormData; we borrow Node's
// (undici) globals onto the window so app.js's `new Headers(...)` etc. resolve.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { JSDOM } from "jsdom";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP_JS = readFileSync(join(HERE, "..", "..", "static", "app.js"), "utf8");

const DEFAULT_HTML =
  "<!doctype html><html><head></head><body></body></html>";

/**
 * Build a jsdom window, install the requested fetch stub + Node fetch globals,
 * then execute static/app.js in that window's global scope.
 *
 * @param {object}   opts
 * @param {string}   [opts.html]      Document HTML (include the csrf meta tag to arm the wrapper).
 * @param {string}   [opts.url]       Document URL — sets window.location.origin for same/cross-origin checks.
 * @param {Function} [opts.fetchStub] Installed as window.fetch *before* app.js runs, so the wrapper wraps it.
 * @returns {Window} the jsdom window after app.js has run.
 */
export function loadApp({
  html = DEFAULT_HTML,
  url = "https://app.example.test/",
  fetchStub,
} = {}) {
  const dom = new JSDOM(html, { url, runScripts: "outside-only" });
  const { window } = dom;

  // jsdom lacks these; app.js's CSRF wrapper + bulk uploader use them.
  window.Headers = globalThis.Headers;
  window.FormData = globalThis.FormData;
  if (fetchStub) window.fetch = fetchStub;

  // Run the real source in the jsdom global scope — bare `document` / `window`
  // references resolve to this window's globals.
  window.eval(APP_JS);
  return window;
}

/** A fetch stub that records its calls and resolves to a minimal ok Response. */
export function recordingFetch() {
  const calls = [];
  const fn = (input, init) => {
    calls.push({ input, init });
    return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
  };
  fn.calls = calls;
  return fn;
}
