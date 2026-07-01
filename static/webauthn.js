// Passkey (WebAuthn) client ceremonies — issue #267.
//
// Registration happens on the Account page ([data-webauthn-register]);
// sign-in happens on the login page ([data-webauthn-login]), using a
// discoverable/resident credential so no username is typed first — the
// browser's own passkey picker resolves the account.
//
// Self-contained CSRF: reads <meta name="csrf-token"> directly rather than
// relying on app.js's fetch wrapper, because the unauthenticated login shell
// (auth/_shell.html) doesn't load app.js.
//
// Both buttons render `hidden` server-side and are only un-hidden here if
// the browser actually supports WebAuthn — fail-safe progressive
// enhancement, same pattern as the type-to-confirm dialog in app.js.
(function () {
  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') || '' : '';
  }

  function postJSON(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify(body || {}),
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (!resp.ok) throw new Error((data && data.error) || 'Request failed.');
        return data;
      });
    });
  }

  function base64urlToBuffer(str) {
    var pad = '===='.slice((str.length + 3) % 4);
    var base64 = (str + pad).replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(base64);
    var buf = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
    return buf.buffer;
  }

  function bufferToBase64url(buf) {
    var bytes = new Uint8Array(buf);
    var str = '';
    for (var i = 0; i < bytes.length; i++) str += String.fromCharCode(bytes[i]);
    return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function decodeCreationOptions(options) {
    options.challenge = base64urlToBuffer(options.challenge);
    options.user.id = base64urlToBuffer(options.user.id);
    (options.excludeCredentials || []).forEach(function (c) { c.id = base64urlToBuffer(c.id); });
    return options;
  }

  function decodeRequestOptions(options) {
    options.challenge = base64urlToBuffer(options.challenge);
    (options.allowCredentials || []).forEach(function (c) { c.id = base64urlToBuffer(c.id); });
    return options;
  }

  function setStatus(el, message) {
    if (!el) return;
    el.textContent = message;
    el.hidden = false;
  }

  function wireRegister() {
    var btn = document.querySelector('[data-webauthn-register]');
    if (!btn) return;
    var statusEl = document.querySelector('[data-webauthn-register-status]');
    btn.hidden = false;

    btn.addEventListener('click', function () {
      btn.disabled = true;
      if (statusEl) statusEl.hidden = true;
      postJSON(btn.getAttribute('data-endpoint-options'))
        .then(function (options) {
          return navigator.credentials.create({ publicKey: decodeCreationOptions(options) });
        })
        .then(function (credential) {
          return postJSON(btn.getAttribute('data-endpoint-verify'), {
            id: credential.id,
            rawId: bufferToBase64url(credential.rawId),
            type: credential.type,
            response: {
              clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
              attestationObject: bufferToBase64url(credential.response.attestationObject),
            },
            nickname: (navigator.platform || 'Passkey').slice(0, 100),
          });
        })
        .then(function () { window.location.reload(); })
        .catch(function (err) {
          btn.disabled = false;
          setStatus(statusEl, (err && err.name === 'NotAllowedError')
            ? 'Cancelled.' : 'Couldn\'t add that passkey. Try again.');
        });
    });
  }

  function wireLogin() {
    var btn = document.querySelector('[data-webauthn-login]');
    if (!btn) return;
    var statusEl = document.querySelector('[data-webauthn-login-status]');
    btn.hidden = false;

    btn.addEventListener('click', function () {
      btn.disabled = true;
      if (statusEl) statusEl.hidden = true;
      postJSON(btn.getAttribute('data-endpoint-options'))
        .then(function (options) {
          return navigator.credentials.get({ publicKey: decodeRequestOptions(options) });
        })
        .then(function (credential) {
          return postJSON(btn.getAttribute('data-endpoint-verify'), {
            id: credential.id,
            rawId: bufferToBase64url(credential.rawId),
            type: credential.type,
            response: {
              clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
              authenticatorData: bufferToBase64url(credential.response.authenticatorData),
              signature: bufferToBase64url(credential.response.signature),
              userHandle: credential.response.userHandle
                ? bufferToBase64url(credential.response.userHandle) : null,
            },
          });
        })
        .then(function (data) { window.location.href = (data && data.next) || '/'; })
        .catch(function (err) {
          btn.disabled = false;
          setStatus(statusEl, (err && err.name === 'NotAllowedError')
            ? 'Cancelled.' : 'Passkey sign-in didn\'t complete. Use your password instead.');
        });
    });
  }

  function init() {
    // PublicKeyCredential existing is enough to attempt a discoverable-
    // credential ceremony; browsers without support simply leave the button
    // hidden (set in HTML, never un-hidden here).
    if (!window.PublicKeyCredential) return;
    wireRegister();
    wireLogin();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
