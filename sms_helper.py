"""Twilio SMS / WhatsApp helper.

Mirrors ``email_helper.send_email``: a single send entry point per channel,
hitting Twilio's REST API directly via ``requests`` so we don't pull in the
``twilio`` SDK for two POST calls. WhatsApp reuses the same Messages
endpoint as SMS — Twilio just wants both ``To`` and ``From`` prefixed with
``whatsapp:``.

Env vars:
- ``TWILIO_ACCOUNT_SID`` / ``TWILIO_AUTH_TOKEN`` — required for live sending
  (HTTP Basic Auth on the Twilio API). Without them, both senders return
  False after printing the message to stdout — same dev/preview fallback as
  ``email_helper``.
- ``TWILIO_SMS_FROM``      — required for SMS. A Twilio phone number in
  E.164 form (``+15551234567``).
- ``TWILIO_WHATSAPP_FROM`` — required for WhatsApp. A WhatsApp-enabled
  Twilio sender, E.164 form (no ``whatsapp:`` prefix — added here).
"""
import os

import requests

_TWILIO_MESSAGES_URL = 'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'


def _credentials() -> tuple[str, str]:
    return (
        os.environ.get('TWILIO_ACCOUNT_SID', '').strip(),
        os.environ.get('TWILIO_AUTH_TOKEN', '').strip(),
    )


def sms_configured() -> bool:
    """True only when account creds and an SMS-from number are set. Routes
    can surface a clearer error than a 500 from a missing env var."""
    sid, token = _credentials()
    return bool(sid and token and os.environ.get('TWILIO_SMS_FROM', '').strip())


def whatsapp_configured() -> bool:
    """True only when account creds and a WhatsApp-from sender are set."""
    sid, token = _credentials()
    return bool(sid and token and os.environ.get('TWILIO_WHATSAPP_FROM', '').strip())


def _send(to_number: str, body: str, *, from_env: str, whatsapp: bool, log_tag: str) -> bool:
    sid, token = _credentials()
    from_number = os.environ.get(from_env, '').strip()
    if not sid or not token or not from_number:
        # Dev / unconfigured fallback: dump the message to stdout so invite
        # flows are still testable without live Twilio credentials.
        print(f'[{log_tag}:unconfigured] to={to_number}')
        print(body)
        return False

    to_value = f'whatsapp:{to_number}' if whatsapp else to_number
    from_value = f'whatsapp:{from_number}' if whatsapp else from_number
    try:
        resp = requests.post(
            _TWILIO_MESSAGES_URL.format(sid=sid),
            auth=(sid, token),
            data={'To': to_value, 'From': from_value, 'Body': body},
            timeout=10,
        )
    except requests.RequestException as e:
        print(f'[{log_tag}:send_failed] to={to_number} err={e}')
        return False

    if 200 <= resp.status_code < 300:
        print(f'[{log_tag}:sent] to={to_number} status={resp.status_code}')
        return True
    print(f'[{log_tag}:twilio_rejected] to={to_number} '
          f'status={resp.status_code} body={resp.text[:200]}')
    return False


def send_sms(to_number: str, body: str) -> bool:
    """Send a plain SMS via Twilio. Returns True on a 2xx, False otherwise."""
    return _send(to_number, body, from_env='TWILIO_SMS_FROM', whatsapp=False, log_tag='sms')


def send_whatsapp(to_number: str, body: str) -> bool:
    """Send a WhatsApp message via Twilio. Returns True on a 2xx, False otherwise."""
    return _send(to_number, body, from_env='TWILIO_WHATSAPP_FROM', whatsapp=True, log_tag='whatsapp')
