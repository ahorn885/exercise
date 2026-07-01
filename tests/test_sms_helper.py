"""Unit coverage for the Twilio SMS / WhatsApp helper (`sms_helper.py`, #272).

Mirrors how `email_helper.send_email` would be tested: env-var gating, the
unconfigured stdout fallback, and the success/4xx/network-error outcomes off
a mocked `requests.post` — no live Twilio calls.
"""

from __future__ import annotations

import requests

import sms_helper


class _Resp:
    def __init__(self, status_code, text=''):
        self.status_code = status_code
        self.text = text


def _env(monkeypatch, *, sid='AC123', token='secret', sms_from=None, whatsapp_from=None):
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', sid)
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', token)
    if sms_from is not None:
        monkeypatch.setenv('TWILIO_SMS_FROM', sms_from)
    else:
        monkeypatch.delenv('TWILIO_SMS_FROM', raising=False)
    if whatsapp_from is not None:
        monkeypatch.setenv('TWILIO_WHATSAPP_FROM', whatsapp_from)
    else:
        monkeypatch.delenv('TWILIO_WHATSAPP_FROM', raising=False)


class TestConfigured:
    def test_sms_configured_true_when_all_set(self, monkeypatch):
        _env(monkeypatch, sms_from='+15550000000')
        assert sms_helper.sms_configured() is True

    def test_sms_configured_false_when_from_missing(self, monkeypatch):
        _env(monkeypatch)
        assert sms_helper.sms_configured() is False

    def test_whatsapp_configured_true_when_all_set(self, monkeypatch):
        _env(monkeypatch, whatsapp_from='+15550000000')
        assert sms_helper.whatsapp_configured() is True

    def test_whatsapp_configured_false_when_creds_missing(self, monkeypatch):
        monkeypatch.delenv('TWILIO_ACCOUNT_SID', raising=False)
        monkeypatch.delenv('TWILIO_AUTH_TOKEN', raising=False)
        monkeypatch.setenv('TWILIO_WHATSAPP_FROM', '+15550000000')
        assert sms_helper.whatsapp_configured() is False


class TestSendSms:
    def test_unconfigured_falls_back_to_stdout(self, monkeypatch, capsys):
        _env(monkeypatch)  # no TWILIO_SMS_FROM
        assert sms_helper.send_sms('+15551234567', 'hello') is False
        out = capsys.readouterr().out
        assert '[sms:unconfigured]' in out
        assert 'hello' in out

    def test_sends_plain_number_on_success(self, monkeypatch):
        _env(monkeypatch, sms_from='+15550000000')
        captured = {}

        def fake_post(url, auth, data, timeout):
            captured.update(url=url, auth=auth, data=data, timeout=timeout)
            return _Resp(201)

        monkeypatch.setattr(requests, 'post', fake_post)
        assert sms_helper.send_sms('+15551234567', 'hello') is True
        assert captured['data']['To'] == '+15551234567'
        assert captured['data']['From'] == '+15550000000'
        assert captured['auth'] == ('AC123', 'secret')
        assert 'AC123' in captured['url']

    def test_twilio_rejection_returns_false(self, monkeypatch):
        _env(monkeypatch, sms_from='+15550000000')
        monkeypatch.setattr(requests, 'post', lambda *a, **k: _Resp(400, 'bad number'))
        assert sms_helper.send_sms('+1555', 'hello') is False

    def test_network_error_returns_false(self, monkeypatch):
        _env(monkeypatch, sms_from='+15550000000')

        def raise_it(*a, **k):
            raise requests.RequestException('boom')

        monkeypatch.setattr(requests, 'post', raise_it)
        assert sms_helper.send_sms('+15551234567', 'hello') is False


class TestSendWhatsapp:
    def test_unconfigured_falls_back_to_stdout(self, monkeypatch, capsys):
        _env(monkeypatch)  # no TWILIO_WHATSAPP_FROM
        assert sms_helper.send_whatsapp('+15551234567', 'hello') is False
        out = capsys.readouterr().out
        assert '[whatsapp:unconfigured]' in out

    def test_prefixes_to_and_from_with_whatsapp(self, monkeypatch):
        _env(monkeypatch, whatsapp_from='+15550000000')
        captured = {}

        def fake_post(url, auth, data, timeout):
            captured.update(data=data)
            return _Resp(201)

        monkeypatch.setattr(requests, 'post', fake_post)
        assert sms_helper.send_whatsapp('+15551234567', 'hello') is True
        assert captured['data']['To'] == 'whatsapp:+15551234567'
        assert captured['data']['From'] == 'whatsapp:+15550000000'
