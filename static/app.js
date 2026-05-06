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
