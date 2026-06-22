"""Transactional email rendering.

Renders the shared-shell HTML + plaintext templates that live in ``email/``
(designed by Claude Design — see ``email/HANDOFF.md`` and ``email/manifest.json``)
and supplies the shell context (logo URL, support address, company address)
that every template needs. Six templates today: ``confirm-email``,
``password-reset``, ``plan-ready``, ``plan-failed``, ``password-changed``,
``email-changed``.

Kept separate from ``email_helper.send_email`` (the SendGrid transport) so the
content layer and the wire layer stay independent: callers render here, then
hand the ``(html, text)`` pair to ``send_email``.

Templates use ``{{ variable }}`` placeholders and are rendered with Jinja2.
HTML parts are autoescaped (so user-controlled values like ``plan_name`` /
``display_name`` can't inject markup); the ``.txt`` parts are not (raw URLs
must stay raw). Shell variables come from env so they're configurable per
deploy without touching the design files:

- ``PUBLIC_BASE_URL``       — absolute origin for links/assets rendered outside
                              a request (the plan emails can fire from cron,
                              where ``url_for(_external=True)`` has no host).
                              Defaults to the prod custom domain.
- ``EMAIL_SUPPORT_ADDRESS`` — the ``{{support_email}}`` shown in every footer.
- ``EMAIL_COMPANY_ADDRESS`` — the ``{{company_address}}`` postal line; the
                              footer omits the separator when it's unset.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, select_autoescape

_EMAIL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'email')

# Prod custom domain (recorded in repo history). Override with PUBLIC_BASE_URL.
_DEFAULT_BASE_URL = 'https://app.aidstation.pro'
_DEFAULT_SUPPORT = 'support@aidstation.pro'


def public_base_url() -> str:
    """Absolute, scheme-qualified origin used to build asset/link URLs in mail
    that may be rendered with no request context (e.g. plan emails from cron)."""
    return (os.environ.get('PUBLIC_BASE_URL') or _DEFAULT_BASE_URL).rstrip('/')


def logo_url() -> str:
    """Absolute URL for the header lockup. The PNG ships in ``static/email/`` so
    the app serves it; email clients can't load relative ``src`` paths."""
    return public_base_url() + '/static/email/aidstation-lockup.png'


def account_security_url() -> str:
    """Target for the security receipts' "Secure your account" link. Prefers a
    request-built URL; falls back to the configured origin + account path when
    there's no app/request context."""
    try:
        from flask import url_for
        return url_for('profile.account_settings', _external=True)
    except Exception:  # noqa: BLE001 — no-context fallback keeps the link usable
        return public_base_url() + '/profile/account'


def format_timestamp(dt: datetime | None = None) -> str:
    """Preformatted UTC stamp for the receipts, e.g. ``22 Jun 2026, 14:32 UTC``.
    ``%-d`` isn't portable, so the day is composed by hand."""
    dt = dt or datetime.now(timezone.utc)
    return f"{dt.day} {dt.strftime('%b %Y, %H:%M')} UTC"


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_EMAIL_DIR),
        autoescape=select_autoescape(enabled_extensions=('html',),
                                     default_for_string=False),
    )


def _shell_context() -> dict:
    return {
        'logo_url': logo_url(),
        'support_email': os.environ.get('EMAIL_SUPPORT_ADDRESS', _DEFAULT_SUPPORT),
        'company_address': (os.environ.get('EMAIL_COMPANY_ADDRESS') or '').strip(),
    }


def render_email(template_id: str, **context) -> tuple[str, str]:
    """Render ``(html, text)`` for one template id (e.g. ``'password-reset'``).

    Shell variables (logo, support, address) are injected automatically; pass
    only the per-template variables documented in ``email/manifest.json``.
    """
    ctx = _shell_context()
    ctx.update(context)
    env = _env()
    html = env.get_template(f'{template_id}.html').render(ctx)
    text = env.get_template(f'text/{template_id}.txt').render(ctx)
    return html, text
