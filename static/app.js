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
    var el = e.target;
    while (el && el !== document) {
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

