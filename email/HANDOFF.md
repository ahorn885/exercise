# AIDSTATION — Transactional Email Templates · Implementation Handoff

Six transactional emails, each with an **HTML** and a **plaintext** part. They share one visual shell (logo header + elevation motif + footer) so they don't drift back into copy-paste.

> **For the implementer (Claude Code):** Adapt these into the shared email shell used by `email_helper.py`. Lift the markup as-is; the only required edit before sending is the logo `src` (see Shell notes). Variable names below match the backend call sites given.

---

## Token syntax

Placeholders are written as `{{ variable }}` (double brace) in both HTML and text. They are **CSS-safe** — there are no single-brace collisions with the `<style>` block, so you can render with Jinja2, Handlebars, or a simple regex replace. If you render with Python `str.format()` instead, swap `{{x}}` → `{x}` AND escape the literal braces inside the `<style>` block.

The backend call sites pass these names; render both the HTML and text part with the same context.

---

## The set

| # | File (HTML / text) | Trigger · code ref | Subject | CTA |
|---|---|---|---|---|
| 1 | `confirm-email` | 5 triggers — `routes/auth.py:631` | `AIDSTATION — confirm your email` | Confirm email → `verify_url` |
| 2 | `password-reset` | `routes/auth.py:533` | `AIDSTATION — password reset` | Set a new password → `reset_url` |
| 3 | `plan-ready` | `plan_notifications.py:91` | `AIDSTATION — your plan "{{plan_name}}" is ready` | View your plan → `plan_url` |
| 4 | `plan-failed` | `plan_notifications.py:91` | `AIDSTATION — couldn't generate "{{plan_name}}"` | Try again → `retry_url` |
| 5 | `password-changed` | `routes/auth.py` (post-reset / mfa.disable / session.clear) | `AIDSTATION — your password was changed` | *(no primary CTA)* Secure your account → `security_url` |
| 6 | `email-changed` ⭐ NEW | `routes/profile.py:1223` — **send to OLD address** | `AIDSTATION — your email address was changed` | *(no primary CTA)* Secure your account → `security_url` |

HTML files: `emails/<name>.html` · Plaintext: `emails/text/<name>.txt`

---

## Variables per template

| Template | Variables |
|---|---|
| confirm-email | `verify_url`, `expiry` *(no greeting — see note)* |
| password-reset | `display_name`, `reset_url`, `expiry` |
| plan-ready | `display_name`, `plan_name`, `plan_url` |
| plan-failed | `display_name`, `plan_name`, `error_message`, `retry_url` |
| password-changed | `display_name`, `timestamp` |
| email-changed | `display_name`, `old_email`, `new_email`, `timestamp` |
| **Shell (all)** | `support_email`, `company_address`, `security_url` *(receipts 5 & 6 only)* |

`expiry` is a **preformatted human string** (e.g. `"30 minutes"`, `"24 hours"`) — the templates print it verbatim, so format it at the call site. Reset = 30 min, confirm = hours.

`timestamp` is also preformatted (e.g. `"21 Jun 2026, 14:32 UTC"`).

---

## Decisions baked in

- **Confirm-email has no greeting / name.** One template serves all 5 triggers (register, email-change, resend, Oura, Wahoo), and a name isn't available on every path. Copy is written to read cleanly with zero personalization. *(If you later split the register path and want "Hi {{display_name}}," there's room above the CTA — but the shared template stays nameless.)*
- **Security receipts (5 & 6) have no primary CTA.** They lead with a "wasn't you?" line and a support/secure-account path, per receipt convention — not a big orange button competing with the message. The "Secure your account" link is a secondary ghost button → `security_url`.
- **Email-changed goes to the OLD address.** This is the anti-takeover guard and the one genuinely new send. It lists both old and new addresses so the original owner can act. Optionally also send a plain confirmation to the new address (not designed here — say the word).

---

## Shell notes (apply once, to all six)

1. **Logo must be an absolute URL.** Each header has `<img src="aidstation-lockup.png" …>`. Host `emails/aidstation-lockup.png` on your CDN/S3 and replace the `src` with the absolute URL (e.g. `https://aidstation.pro/email/aidstation-lockup.png`). Email clients can't load relative paths. Keep the `alt="AIDSTATION"` and `width`/`height`.
2. **Dark theme.** Templates declare `color-scheme: dark` and set explicit hex on every cell, so they're legible whether or not a client honors dark mode. No oklch — all hex, per your constraint.
3. **Outlook.** Table-based layout with VML/`mso` guards already in the `<head>`. Buttons are bordered table cells (no VML roundrect needed at this radius).
4. **Both parts.** `email_helper.py:57` sends HTML + text; pair each `.html` with its `.txt`. The plaintext mirrors the HTML content and link targets exactly.
5. **Suppression.** These are transactional (account + security) — keep them off marketing suppression groups so a reset or takeover notice always lands. No unsubscribe link is included (correct for transactional).

---

## Files

```
emails/
  confirm-email.html      email-changed.html
  password-reset.html     password-changed.html
  plan-ready.html         plan-failed.html
  aidstation-lockup.png   ← host this, update <img src>
  manifest.json           ← machine-readable spec (below)
  text/
    confirm-email.txt     email-changed.txt
    password-reset.txt    password-changed.txt
    plan-ready.txt        plan-failed.txt
```

`manifest.json` carries the same spec as structured data — point Claude Code at it for programmatic wiring.
