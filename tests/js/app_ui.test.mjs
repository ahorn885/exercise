// Coverage for two more self-contained app.js modules (#231): the delegated
// data-confirm guard and the theme toggle. Proves the harness reaches DOM
// event + mutation behaviour, not just the fetch wrapper.
import test from "node:test";
import assert from "node:assert/strict";

import { loadApp } from "./helpers.mjs";

const page = (body) =>
  `<!doctype html><html><head></head><body>${body}</body></html>`;

test("data-confirm cancels submit when the user dismisses", () => {
  const w = loadApp({
    html: page('<form id="f" data-confirm="Sure?"><button type="submit">Go</button></form>'),
  });
  w.confirm = () => false;
  const ev = new w.Event("submit", { bubbles: true, cancelable: true });
  w.document.getElementById("f").dispatchEvent(ev);
  assert.equal(ev.defaultPrevented, true);
});

test("data-confirm allows submit when the user accepts", () => {
  const w = loadApp({
    html: page('<form id="f" data-confirm="Sure?"><button type="submit">Go</button></form>'),
  });
  w.confirm = () => true;
  const ev = new w.Event("submit", { bubbles: true, cancelable: true });
  w.document.getElementById("f").dispatchEvent(ev);
  assert.equal(ev.defaultPrevented, false);
});

test("data-confirm on a click target cancels the action when dismissed", () => {
  const w = loadApp({
    html: page('<a id="a" href="/x" data-confirm="Leave?">link</a>'),
  });
  w.confirm = () => false;
  const ev = new w.MouseEvent("click", { bubbles: true, cancelable: true });
  w.document.getElementById("a").dispatchEvent(ev);
  assert.equal(ev.defaultPrevented, true);
});

test("theme toggle flips the documentElement class and persists it", () => {
  const w = loadApp({ html: page('<button data-theme-toggle>theme</button>') });
  const root = w.document.documentElement;
  const wasLight = root.classList.contains("theme-light");

  w.document
    .querySelector("[data-theme-toggle]")
    .dispatchEvent(new w.MouseEvent("click", { bubbles: true }));

  assert.equal(root.classList.contains("theme-light"), !wasLight);
  assert.equal(
    w.localStorage.getItem("aidstation-theme"),
    !wasLight ? "light" : "dark",
  );
});

test("theme toggle syncs aria-pressed on the control", () => {
  const w = loadApp({ html: page('<button data-theme-toggle>theme</button>') });
  const btn = w.document.querySelector("[data-theme-toggle]");
  const before = btn.getAttribute("aria-pressed");
  btn.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  assert.notEqual(btn.getAttribute("aria-pressed"), before);
});
