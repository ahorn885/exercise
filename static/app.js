// Auto-inject CSRF header on same-origin state-changing fetches. The token
// is rendered into <meta name="csrf-token"> by base.html / _shell.html;
// Flask-WTF accepts it as the X-CSRFToken header (see app.py CSRFProtect).
// Wrapping fetch keeps the existing call sites unchanged.
(function () {
  var meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta) return;
  var token = meta.getAttribute('content') || '';
  if (!token) return;

  var unsafe = {POST: 1, PUT: 1, PATCH: 1, DELETE: 1};
  var origFetch = window.fetch;
  if (!origFetch) return;

  window.fetch = function (input, init) {
    init = init || {};
    var method = (init.method || (typeof input !== 'string' && input.method) || 'GET').toUpperCase();
    if (!unsafe[method]) return origFetch(input, init);

    // Skip cross-origin requests — only same-origin POSTs need the token,
    // and adding it to outbound 3rd-party calls would leak it.
    var url = typeof input === 'string' ? input : input.url;
    try {
      var u = new URL(url, window.location.href);
      if (u.origin !== window.location.origin) return origFetch(input, init);
    } catch (_) { /* relative URL — same-origin by construction */ }

    var headers = new Headers(init.headers || (typeof input !== 'string' ? input.headers : undefined) || {});
    if (!headers.has('X-CSRFToken')) headers.set('X-CSRFToken', token);
    init.headers = headers;
    return origFetch(input, init);
  };
})();

// Delegated confirm() handler. Inline onsubmit/onclick="return confirm(...)"
// got refactored to data-confirm="..." (CSP nonce migration) so we don't
// need 'unsafe-inline' on script-src. The semantics are identical:
//  - <form data-confirm="...">     → submit cancelled if user dismisses
//  - <a data-confirm="...">        → navigation cancelled if user dismisses
//  - <button data-confirm="...">   → click cancelled (form submit too)
(function () {
  document.addEventListener('submit', function (e) {
    var msg = e.target && e.target.dataset && e.target.dataset.confirm;
    if (msg && !window.confirm(msg)) e.preventDefault();
  }, true);

  document.addEventListener('click', function (e) {
    // Walk up to the nearest element with data-confirm so a click on a
    // child <span> inside a button/anchor still triggers the prompt.
    // Stop at <form> — the submit handler above owns form-level
    // data-confirm; walking through would double-prompt (once here on
    // the submit-button click, again when the form's submit fires).
    var el = e.target;
    while (el && el !== document) {
      if (el.tagName === 'FORM') return;
      if (el.dataset && el.dataset.confirm) {
        if (!window.confirm(el.dataset.confirm)) {
          e.preventDefault();
          e.stopPropagation();
        }
        return;
      }
      el = el.parentNode;
    }
  }, true);
})();

// data-autosubmit: a <select> or <input> that should submit its enclosing
// form when changed. Replaces inline onchange="this.form.submit()".
(function () {
  document.addEventListener('change', function (e) {
    var el = e.target;
    if (el && el.dataset && 'autosubmit' in el.dataset && el.form) {
      el.form.submit();
    }
  });
})();

// Bulk FIT uploader. Activated on any [data-bulk-upload] container: collects
// many files (multi-select, folder pick, or drag-and-drop), filters to the
// accepted extensions, then POSTs them to data-endpoint in size-bounded
// batches (Vercel caps request bodies ~4.5 MB), rendering a running summary.
// The CSRF header is added by the fetch wrapper above. Server returns
// {summary:{...counts}, results:[{name,status,detail}]}.
(function () {
  var MAX_BYTES = 3.5 * 1024 * 1024;   // per-request payload ceiling
  var MAX_FILES = 40;                  // per-request file ceiling
  var MAX_ROWS = 400;                  // cap rendered per-file lines

  function fmtBytes(n) {
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(0) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }

  function badge(status) {
    var map = {
      imported: 'bg-success', duplicate: 'bg-secondary',
      skipped: 'bg-warning text-dark', error: 'bg-danger'
    };
    var span = document.createElement('span');
    span.className = 'badge ' + (map[status] || 'bg-secondary') + ' me-2 flex-shrink-0';
    span.textContent = status;
    return span;
  }

  function initOne(root) {
    var endpoint = root.getAttribute('data-endpoint');
    if (!endpoint) return;
    var accept = (root.getAttribute('data-accept') || '.fit,.zip')
      .split(',').map(function (s) { return s.trim().toLowerCase(); })
      .filter(Boolean);

    var q = function (sel) { return root.querySelector(sel); };
    var drop = q('[data-bulk-drop]');
    var selectionEl = q('[data-bulk-selection]');
    var startBtn = q('[data-bulk-start]');
    var progressWrap = q('[data-bulk-progress]');
    var bar = q('[data-bulk-bar]');
    var progressText = q('[data-bulk-progress-text]');
    var summaryEl = q('[data-bulk-summary]');
    var resultsEl = q('[data-bulk-results]');
    var inputs = Array.prototype.slice.call(
      root.querySelectorAll('[data-bulk-files], [data-bulk-folder]'));

    var selected = [];
    var rendered = 0;

    function accepted(name) {
      name = (name || '').toLowerCase();
      return accept.some(function (ext) { return name.endsWith(ext); });
    }

    function setSelection(fileList) {
      selected = Array.prototype.slice.call(fileList).filter(function (f) {
        return accepted(f.name);
      });
      var bytes = selected.reduce(function (a, f) { return a + f.size; }, 0);
      if (selectionEl) {
        selectionEl.textContent = selected.length
          ? selected.length + ' file' + (selected.length === 1 ? '' : 's')
            + ' ready (' + fmtBytes(bytes) + ')'
          : 'No matching files selected.';
      }
      if (startBtn) {
        startBtn.disabled = selected.length === 0;
        startBtn.textContent = 'Import ' + selected.length + ' file'
          + (selected.length === 1 ? '' : 's');
      }
    }

    function makeBatches() {
      var batches = [], cur = [], curBytes = 0;
      selected.forEach(function (f) {
        if (cur.length && (cur.length >= MAX_FILES || curBytes + f.size > MAX_BYTES)) {
          batches.push(cur); cur = []; curBytes = 0;
        }
        cur.push(f); curBytes += f.size;
      });
      if (cur.length) batches.push(cur);
      return batches;
    }

    function renderResults(rows) {
      if (!resultsEl) return;
      rows.forEach(function (r) {
        if (rendered >= MAX_ROWS) return;
        var line = document.createElement('div');
        line.className = 'd-flex align-items-start mb-1';
        line.appendChild(badge(r.status));
        var txt = document.createElement('span');
        txt.className = 'text-break';
        txt.textContent = (r.name || '') + (r.detail ? ' — ' + r.detail : '');
        line.appendChild(txt);
        resultsEl.appendChild(line);
        rendered += 1;
        if (rendered === MAX_ROWS) {
          var more = document.createElement('div');
          more.className = 'text-muted fst-italic mt-1';
          more.textContent = '(further per-file lines hidden — totals above are complete)';
          resultsEl.appendChild(more);
        }
      });
    }

    function renderSummary(s) {
      if (!summaryEl) return;
      var order = [
        ['imported', 'Imported', 'text-bg-success'],
        ['matched', 'Matched to plan', 'text-bg-primary'],
        ['duplicates', 'Duplicates', 'text-bg-secondary'],
        ['skipped', 'Skipped', 'text-bg-warning'],
        ['errors', 'Errors', 'text-bg-danger'],
        ['files', 'Files', 'text-bg-info']
      ];
      summaryEl.textContent = '';
      var wrap = document.createElement('div');
      wrap.className = 'd-flex flex-wrap gap-2';
      order.forEach(function (o) {
        if (!(o[0] in s)) return;
        var b = document.createElement('span');
        b.className = 'badge ' + o[2];
        b.textContent = o[1] + ': ' + (s[o[0]] || 0);
        wrap.appendChild(b);
      });
      summaryEl.appendChild(wrap);
    }

    function setProgress(done, total) {
      if (bar) bar.style.width = (total ? Math.round(done / total * 100) : 0) + '%';
      if (progressText) progressText.textContent = done + ' / ' + total + ' files processed';
    }

    function appendFields(fd) {
      // Include any [data-bulk-field] inputs (e.g. the match-to-plan toggle)
      // with every batch. Checkboxes send '1' when checked, '0' otherwise.
      root.querySelectorAll('[data-bulk-field]').forEach(function (el) {
        if (!el.name) return;
        var val = el.type === 'checkbox' ? (el.checked ? '1' : '0') : el.value;
        fd.append(el.name, val);
      });
    }

    function run() {
      if (!selected.length) return;
      // Best-effort chronological order across batches: Garmin export
      // filenames are date-prefixed, so a name sort approximates it. Keeps
      // plan-matching and rx progression sane when many files span batches.
      selected.sort(function (a, b) {
        return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0);
      });
      var total = selected.length;
      var batches = makeBatches();
      var running = {};
      var done = 0;
      if (resultsEl) resultsEl.textContent = '';
      rendered = 0;
      if (summaryEl) summaryEl.textContent = '';
      if (progressWrap) progressWrap.classList.remove('d-none');
      setProgress(0, total);
      if (startBtn) startBtn.disabled = true;
      inputs.forEach(function (inp) { inp.disabled = true; });

      var i = 0;
      function finish() {
        if (startBtn) {
          startBtn.disabled = false;
          startBtn.textContent = 'Import more';
        }
        inputs.forEach(function (inp) { inp.disabled = false; });
        selected = [];
      }
      function next() {
        if (i >= batches.length) { finish(); return; }
        var batch = batches[i++];
        var fd = new FormData();
        batch.forEach(function (f) { fd.append('files', f, f.name); });
        appendFields(fd);
        fetch(endpoint, { method: 'POST', body: fd })
          .then(function (resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
          })
          .then(function (data) {
            var s = (data && data.summary) || {};
            Object.keys(s).forEach(function (k) {
              running[k] = (running[k] || 0) + (s[k] || 0);
            });
            renderSummary(running);
            renderResults((data && data.results) || []);
          })
          .catch(function (e) {
            running.errors = (running.errors || 0) + batch.length;
            renderSummary(running);
            renderResults(batch.map(function (f) {
              return { name: f.name, status: 'error', detail: String(e.message || e) };
            }));
          })
          .then(function () {
            done += batch.length;
            setProgress(done, total);
            next();
          });
      }
      next();
    }

    inputs.forEach(function (inp) {
      inp.addEventListener('change', function () { setSelection(inp.files); });
    });
    if (startBtn) startBtn.addEventListener('click', run);
    if (drop) {
      ['dragenter', 'dragover'].forEach(function (ev) {
        drop.addEventListener(ev, function (e) {
          e.preventDefault(); e.stopPropagation();
          drop.classList.add('u-drop-active');
        });
      });
      ['dragleave', 'drop'].forEach(function (ev) {
        drop.addEventListener(ev, function (e) {
          e.preventDefault(); e.stopPropagation();
          drop.classList.remove('u-drop-active');
        });
      });
      drop.addEventListener('drop', function (e) {
        if (e.dataTransfer && e.dataTransfer.files) setSelection(e.dataTransfer.files);
      });
    }

    setSelection([]);
  }

  function initAll() {
    document.querySelectorAll('[data-bulk-upload]').forEach(initOne);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();

// §23 command palette (⌘K) + §24 keyboard-shortcuts cheat sheet. Both are
// client-only overlays rendered hidden by _shell/cmdk.html; this wires
// open / close / filter / keyboard-navigate. No inline handlers (CSP):
// everything keys off the data-* hooks in that partial. The destination
// list is server-rendered (real url_for links) — JS only filters and
// follows, so it can't drift from the routes.
(function () {
  var cmdkRoot = document.querySelector('[data-cmdk-root]');
  var ksRoot = document.querySelector('[data-ks-root]');
  var input = document.querySelector('[data-cmdk-input]');
  var list = document.querySelector('[data-cmdk-list]');
  var emptyEl = document.querySelector('[data-cmdk-empty]');
  var items = list
    ? Array.prototype.slice.call(list.querySelectorAll('[data-cmdk-item]'))
    : [];
  var active = -1;

  function visibleItems() {
    return items.filter(function (it) { return !it.hidden; });
  }
  function setActive(idx) {
    var vis = visibleItems();
    items.forEach(function (it) { it.classList.remove('is-active'); });
    if (!vis.length) { active = -1; return; }
    active = (idx + vis.length) % vis.length;
    var el = vis[active];
    el.classList.add('is-active');
    el.scrollIntoView({ block: 'nearest' });
  }
  function filter(q) {
    q = (q || '').trim().toLowerCase();
    var shown = 0;
    items.forEach(function (it) {
      var label = it.getAttribute('data-cmdk-label') || '';
      var match = !q || label.indexOf(q) !== -1;
      it.hidden = !match;
      if (match) shown += 1;
    });
    if (emptyEl) emptyEl.hidden = shown !== 0;
    setActive(0);
  }
  function openCmdk() {
    if (!cmdkRoot) return;
    closeKs();
    cmdkRoot.hidden = false;
    if (input) { input.value = ''; input.focus(); }
    filter('');
  }
  function closeCmdk() { if (cmdkRoot) cmdkRoot.hidden = true; }
  function gotoActive() {
    var vis = visibleItems();
    if (active < 0 || active >= vis.length) return;
    var a = vis[active].querySelector('a');
    if (a) window.location.href = a.href;
  }
  function openKs() { closeCmdk(); if (ksRoot) ksRoot.hidden = false; }
  function closeKs() { if (ksRoot) ksRoot.hidden = true; }

  function typing(e) {
    var t = e.target;
    return t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' ||
                 t.tagName === 'SELECT' || t.isContentEditable);
  }

  document.addEventListener('keydown', function (e) {
    var k = e.key && e.key.toLowerCase();
    // ⌘K / Ctrl-K toggles the palette from anywhere (incl. inside inputs).
    if ((e.metaKey || e.ctrlKey) && k === 'k') {
      e.preventDefault();
      if (cmdkRoot && cmdkRoot.hidden) openCmdk(); else closeCmdk();
      return;
    }
    // "?" opens the cheat sheet — but not while typing or with an overlay up.
    if (k === '?' && !typing(e) && (!cmdkRoot || cmdkRoot.hidden) &&
        (!ksRoot || ksRoot.hidden)) {
      e.preventDefault();
      openKs();
      return;
    }
    if (cmdkRoot && !cmdkRoot.hidden) {
      if (k === 'escape') { e.preventDefault(); closeCmdk(); }
      else if (k === 'arrowdown') { e.preventDefault(); setActive(active + 1); }
      else if (k === 'arrowup') { e.preventDefault(); setActive(active - 1); }
      else if (k === 'enter') { e.preventDefault(); gotoActive(); }
      return;
    }
    if (ksRoot && !ksRoot.hidden && k === 'escape') { e.preventDefault(); closeKs(); }
  });

  if (input) input.addEventListener('input', function () { filter(input.value); });
  // Hover highlights the row under the pointer so mouse + keyboard agree.
  items.forEach(function (it) {
    it.addEventListener('mousemove', function () {
      var idx = visibleItems().indexOf(it);
      if (idx !== -1) setActive(idx);
    });
  });
  // A click on the backdrop (outside the panel) closes the overlay.
  if (cmdkRoot) cmdkRoot.addEventListener('click', function (e) {
    if (e.target === cmdkRoot) closeCmdk();
  });
  if (ksRoot) ksRoot.addEventListener('click', function (e) {
    if (e.target === ksRoot) closeKs();
  });
  var ksClose = document.querySelector('[data-ks-close]');
  if (ksClose) ksClose.addEventListener('click', closeKs);

  // The topbar search affordance now opens the palette (was a focus stub).
  var trigger = document.querySelector('[data-action="cmdk"]');
  if (trigger) trigger.addEventListener('click', function (e) {
    e.preventDefault();
    openCmdk();
  });
})();

// §25/§29 — type-to-confirm danger dialog with a focus trap. Used by the
// admin delete-user flow: a trigger [data-dialog-open="<id>"] opens the
// matching <div id="<id>" data-dialog>; focus is trapped inside until close
// (Esc, backdrop click, or [data-dialog-close]) and restored to the opener
// afterwards. The submit button [data-typeconfirm-submit] stays disabled
// until the [data-typeconfirm] input exactly matches its
// data-typeconfirm-match value. No JS → the dialog stays hidden and the
// button never enables (fail-safe). CSP-clean: data-* hooks, no inline JS.
(function () {
  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), ' +
    'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  var openDialog = null;
  var lastFocus = null;

  function focusables(root) {
    return Array.prototype.slice.call(root.querySelectorAll(FOCUSABLE))
      .filter(function (el) { return el.offsetParent !== null; });
  }
  function open(dlg) {
    if (!dlg) return;
    lastFocus = document.activeElement;
    dlg.hidden = false;
    openDialog = dlg;
    var f = focusables(dlg);
    if (f.length) f[0].focus();
  }
  function close(dlg) {
    if (!dlg) return;
    dlg.hidden = true;
    if (openDialog === dlg) openDialog = null;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    lastFocus = null;
  }

  document.addEventListener('click', function (e) {
    var opener = e.target.closest && e.target.closest('[data-dialog-open]');
    if (opener) {
      e.preventDefault();
      open(document.getElementById(opener.getAttribute('data-dialog-open')));
      return;
    }
    var closer = e.target.closest && e.target.closest('[data-dialog-close]');
    if (closer && openDialog) { e.preventDefault(); close(openDialog); return; }
    // Backdrop click (outside the .dlg panel) closes.
    if (openDialog && e.target === openDialog) close(openDialog);
  });

  document.addEventListener('keydown', function (e) {
    if (!openDialog) return;
    var k = e.key && e.key.toLowerCase();
    if (k === 'escape') { e.preventDefault(); close(openDialog); return; }
    if (e.key === 'Tab') {
      var f = focusables(openDialog);
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });

  // Type-to-confirm: enable the paired submit only on an exact match.
  Array.prototype.forEach.call(
    document.querySelectorAll('[data-typeconfirm]'), function (input) {
      var form = input.form;
      var btn = form && form.querySelector('[data-typeconfirm-submit]');
      if (!btn) return;
      var want = input.getAttribute('data-typeconfirm-match') || '';
      function sync() { btn.disabled = input.value !== want; }
      input.addEventListener('input', sync);
      sync();
    });
})();

// data-progress="N": set element.style.width to N% on DOM-ready. Used by
// progress bars whose width is computed in Jinja — CSP style-src forbids
// parser-set inline style attributes, so the width is carried in a data-
// attribute and applied by script (script-set styles are not filtered).
(function () {
  function apply() {
    document.querySelectorAll('[data-progress]').forEach(function (el) {
      var v = parseFloat(el.getAttribute('data-progress'));
      if (!isNaN(v)) el.style.width = v + '%';
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply);
  } else {
    apply();
  }
})();

// Theme toggle (§28). The <head> bootstrap (base.html) has already applied the
// saved theme to <html.theme-light> before paint; here we (a) keep every
// [data-theme-toggle] control's pressed-state in sync with the live theme and
// (b) flip + persist on click via event delegation. Toggling a class on
// documentElement is a script-set DOM mutation, not a parser-set inline style,
// so it's CSP-clean.
(function () {
  var KEY = 'aidstation-theme';
  var root = document.documentElement;

  function isLight() { return root.classList.contains('theme-light'); }

  function sync() {
    var light = isLight();
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', light ? 'true' : 'false');
      btn.setAttribute('aria-label', light ? 'Switch to dark mode' : 'Switch to light mode');
    });
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-theme-toggle]');
    if (!btn) return;
    e.preventDefault();
    var light = !isLight();
    root.classList.toggle('theme-light', light);
    try { localStorage.setItem(KEY, light ? 'light' : 'dark'); } catch (_) {}
    sync();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', sync);
  } else {
    sync();
  }
})();

