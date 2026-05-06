"""SendGrid email helper.

Single ``send_email()`` entry point used by every flow that needs to put
mail on the wire (password reset today; invites + verification later).
We hit SendGrid's HTTP API directly via ``requests`` so we don't pull
in another dependency just for one POST.

Env vars:
- ``SENDGRID_API_KEY``  — required for live sending. Without it,
  ``send_email`` returns False after printing the message body to
  stdout, so local dev / preview deploys still surface the reset link
  in logs even when no key is configured.
- ``EMAIL_FROM_ADDRESS`` — required. Must be a verified Single Sender
  or be hosted on a verified Sending Domain in SendGrid; otherwise the
  request 4xx's. Set it to whatever address you verified.
- ``EMAIL_FROM_NAME``    — optional, defaults to ``AIDSTATION``.
"""
import os

import requests

SENDGRID_URL = 'https://api.sendgrid.com/v3/mail/send'


def _from_address() -> tuple[str, str]:
    return (
        os.environ.get('EMAIL_FROM_ADDRESS', '').strip(),
        os.environ.get('EMAIL_FROM_NAME', 'AIDSTATION').strip() or 'AIDSTATION',
    )


def email_configured() -> bool:
    """True only when both API key and from-address are set. Routes can
    surface a clearer error than a 500 from a missing env var."""
    api_key = os.environ.get('SENDGRID_API_KEY', '').strip()
    from_addr, _ = _from_address()
    return bool(api_key and from_addr)


def send_email(to_address: str, subject: str, text_body: str,
               html_body: str | None = None) -> bool:
    """Send a transactional email. Returns True on a 2xx, False otherwise.

    ``text_body`` is required; ``html_body`` is optional but recommended.
    SendGrid will fall back to the text part for clients that strip HTML.
    Logs request outcomes to stdout — visible in Vercel function logs.
    """
    api_key = os.environ.get('SENDGRID_API_KEY', '').strip()
    from_addr, from_name = _from_address()
    if not api_key or not from_addr:
        # Dev / unconfigured fallback: dump the email to stdout so flows
        # like password reset are still testable without a SendGrid key.
        print(f'[email:unconfigured] to={to_address} subject={subject!r}')
        print(text_body)
        return False

    content = [{'type': 'text/plain', 'value': text_body}]
    if html_body:
        content.append({'type': 'text/html', 'value': html_body})

    payload = {
        'personalizations': [{'to': [{'email': to_address}]}],
        'from': {'email': from_addr, 'name': from_name},
        'subject': subject,
        'content': content,
    }
    try:
        resp = requests.post(
            SENDGRID_URL,
            headers={'Authorization': f'Bearer {api_key}',
                     'Content-Type': 'application/json'},
            json=payload,
            timeout=10,
        )
    except requests.RequestException as e:
        print(f'[email:send_failed] to={to_address} err={e}')
        return False

    if 200 <= resp.status_code < 300:
        print(f'[email:sent] to={to_address} subject={subject!r} '
              f'status={resp.status_code}')
        return True
    print(f'[email:sendgrid_rejected] to={to_address} '
          f'status={resp.status_code} body={resp.text[:200]}')
    return False
