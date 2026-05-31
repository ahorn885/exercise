/* AIDSTATION redesign — a11y runtime wiring
   ─────────────────────────────────────────────────────────────────
   Implements the §29 spec against the live DOM. The screens are styled
   divs (a mockup), so rather than hand-edit ~95 artboards we apply the
   ARIA contract + keyboard model by class, and re-apply as the design
   canvas virtualizes artboards in/out of view (MutationObserver).

   Each .screen is enhanced exactly once (guarded). Everything here is
   additive — it never removes content, only adds roles/labels/tabindex
   and key handlers, so it's safe over React's output. */
(function () {
  "use strict";

  var nameOf = function (el) {
    var t = (el.getAttribute("aria-label") || el.getAttribute("data-label") || el.textContent || "").trim();
    return t.replace(/\s+/g, " ");
  };

  // Activate a mock control with keyboard (Enter / Space) → synthesize click,
  // so focus + activation behave like the real control will.
  var keyActivate = function (e) {
    if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      e.currentTarget.click();
    }
  };

  // Roving tabindex for a composite widget (nav list, tab bar). One stop in
  // the page tab order; arrows move within, Home/End jump to ends.
  function makeRoving(container, items, orientation) {
    if (!items.length) return;
    var horizontal = orientation === "horizontal";
    items.forEach(function (it, i) {
      var active = it.getAttribute("aria-current") === "page" || it.classList.contains("active");
      it.setAttribute("tabindex", active ? "0" : "-1");
    });
    // ensure at least one stop
    if (!items.some(function (it) { return it.getAttribute("tabindex") === "0"; })) {
      items[0].setAttribute("tabindex", "0");
    }
    container.addEventListener("keydown", function (e) {
      var idx = items.indexOf(document.activeElement);
      if (idx === -1) return;
      var next = null;
      var fwd = horizontal ? "ArrowRight" : "ArrowDown";
      var bwd = horizontal ? "ArrowLeft" : "ArrowUp";
      if (e.key === fwd) next = items[Math.min(items.length - 1, idx + 1)];
      else if (e.key === bwd) next = items[Math.max(0, idx - 1)];
      else if (e.key === "Home") next = items[0];
      else if (e.key === "End") next = items[items.length - 1];
      if (next) {
        e.preventDefault();
        items.forEach(function (it) { it.setAttribute("tabindex", "-1"); });
        next.setAttribute("tabindex", "0");
        next.focus();
      }
    });
  }

  function enhanceScreen(screen) {
    if (screen.__a11y) return;
    screen.__a11y = true;

    var isMobile = !!screen.querySelector(".tabbar, .appbar, .statusbar");

    // ── Landmarks ──────────────────────────────────────────────
    var sidebar = screen.querySelector(".sidebar");
    if (sidebar) { sidebar.setAttribute("role", "navigation"); sidebar.setAttribute("aria-label", "Primary"); }

    var topbar = screen.querySelector(".topbar");
    if (topbar) topbar.setAttribute("role", "banner");

    var appbar = screen.querySelector(".appbar");
    if (appbar) appbar.setAttribute("role", "banner");

    var main = screen.querySelector(".page-body") || screen.querySelector(".page");
    if (main) main.setAttribute("role", "main");

    var statusbar = screen.querySelector(".statusbar");
    if (statusbar) statusbar.setAttribute("aria-hidden", "true"); // OS chrome, not app content

    // ── Skip link (desktop shells with a sidebar + main) ───────
    if (main && sidebar && !screen.querySelector(".skip-link")) {
      if (!main.id) main.id = "main-" + Math.random().toString(36).slice(2, 8);
      var skip = document.createElement("a");
      skip.className = "skip-link";
      skip.href = "#" + main.id;
      skip.textContent = "Skip to content";
      skip.addEventListener("click", function (e) {
        e.preventDefault();
        main.setAttribute("tabindex", "-1");
        main.focus();
      });
      screen.insertBefore(skip, screen.firstChild);
    }

    // ── Sidebar nav · roving tabindex + aria-current ───────────
    if (sidebar) {
      var navItems = Array.prototype.slice.call(sidebar.querySelectorAll(".sidebar-item"));
      navItems.forEach(function (it) {
        it.setAttribute("role", "link");
        if (it.classList.contains("active")) it.setAttribute("aria-current", "page");
        if (!it.getAttribute("aria-label")) it.setAttribute("aria-label", nameOf(it));
        it.addEventListener("keydown", keyActivate);
      });
      makeRoving(sidebar, navItems, "vertical");

      // account row (footer) — its own button
      var foot = sidebar.querySelector(".sidebar-foot");
      if (foot) {
        foot.setAttribute("role", "button");
        foot.setAttribute("tabindex", "0");
        foot.setAttribute("aria-label", "Account menu");
        foot.setAttribute("aria-haspopup", "menu");
        foot.addEventListener("keydown", keyActivate);
      }
    }

    // ── Top bar search · combobox ──────────────────────────────
    var search = screen.querySelector(".topbar .search");
    if (search) {
      search.setAttribute("role", "combobox");
      search.setAttribute("tabindex", "0");
      search.setAttribute("aria-expanded", "false");
      search.setAttribute("aria-label", "Search");
      search.setAttribute("aria-keyshortcuts", "Meta+K");
      search.addEventListener("keydown", keyActivate);
    }

    // ── Buttons (.btn) — role, focus, name ─────────────────────
    Array.prototype.forEach.call(screen.querySelectorAll(".btn"), function (b) {
      if (b.getAttribute("role")) return;
      b.setAttribute("role", "button");
      b.setAttribute("tabindex", "0");
      var name = nameOf(b);
      if (!name) {
        // icon-only — label from context
        if (b.closest(".topbar") && b.classList.contains("btn-icon")) name = "Notifications";
      }
      if (name) b.setAttribute("aria-label", name);
      b.addEventListener("keydown", keyActivate);
    });

    // ── Stat cards → labelled groups ───────────────────────────
    Array.prototype.forEach.call(screen.querySelectorAll(".stat-card"), function (s) {
      s.setAttribute("role", "group");
      var k = s.querySelector(".k"), v = s.querySelector(".v");
      if (k && v) s.setAttribute("aria-label", nameOf(k) + ": " + nameOf(v));
    });

    // ── Status chips → role=status ─────────────────────────────
    Array.prototype.forEach.call(screen.querySelectorAll(".chip"), function (c) {
      if (/\b(good|warn|bad|accent)\b/.test(c.className)) c.setAttribute("role", "status");
    });

    // ── Tables → header scope ──────────────────────────────────
    Array.prototype.forEach.call(screen.querySelectorAll("table"), function (t) {
      if (!t.getAttribute("role")) t.setAttribute("role", "table");
      Array.prototype.forEach.call(t.querySelectorAll("thead th"), function (th) {
        if (!th.getAttribute("scope")) th.setAttribute("scope", "col");
      });
    });

    // ── Mobile tab bar · nav with roving + aria-current ────────
    var tabbar = screen.querySelector(".tabbar");
    if (tabbar) {
      tabbar.setAttribute("role", "navigation");
      tabbar.setAttribute("aria-label", "Primary");
      var tabs = Array.prototype.slice.call(tabbar.querySelectorAll(".tab"));
      tabs.forEach(function (tab) {
        tab.setAttribute("role", "link");
        if (tab.classList.contains("active")) tab.setAttribute("aria-current", "page");
        if (!tab.getAttribute("aria-label")) tab.setAttribute("aria-label", nameOf(tab));
        tab.addEventListener("keydown", keyActivate);
      });
      makeRoving(tabbar, tabs, "horizontal");
    }

    // ── App bar icon controls (mobile) ─────────────────────────
    if (appbar) {
      var kids = Array.prototype.slice.call(appbar.children);
      kids.forEach(function (kid, i) {
        if (kid.classList && kid.classList.contains("title")) return;
        // first = leading (back/menu), last = trailing action
        kid.setAttribute("role", "button");
        kid.setAttribute("tabindex", "0");
        if (!kid.getAttribute("aria-label")) {
          kid.setAttribute("aria-label", i === 0 ? "Back" : "Action");
        }
        kid.addEventListener("keydown", keyActivate);
      });
    }
  }

  // ── Scan + observe (handles canvas virtualization) ───────────
  var scheduled = false;
  function scan() {
    scheduled = false;
    var screens = document.querySelectorAll(".screen");
    for (var i = 0; i < screens.length; i++) enhanceScreen(screens[i]);
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    (window.requestAnimationFrame || window.setTimeout)(scan, 60);
  }

  function start() {
    scan();
    var root = document.getElementById("root") || document.body;
    new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
  }

  // Give the babel-transpiled canvas time to mount before first pass.
  function boot(n) {
    if (document.querySelector(".screen")) { start(); return; }
    if (n > 200) { start(); return; }
    setTimeout(function () { boot(n + 1); }, 50);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { boot(0); });
  } else {
    boot(0);
  }
})();
