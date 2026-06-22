"""Tests for `plan_notifications.py` — plan-ready/plan-failed email + in-app
badge (#259 / #260).

Self-contained fakes — no live Postgres, no SendGrid. The fake db records SQL
so the tests can assert the atomic claim guard (the poller/cron double-send
defence) and the user-scoping on the read/dismiss paths.
"""

from __future__ import annotations

import plan_notifications as pn


class _Cur:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _FakeRow(dict):
    """dict-like row exposing `.get` (the module reads rows with `.get`)."""


class _RecordingDb:
    """Records every (sql, params); hands back canned responses in order.

    `responses` is a list consulted FIFO per execute; an exhausted list yields a
    cursor with no row (the common "this query doesn't matter here" case)."""

    def __init__(self, responses=None):
        self.calls: list[tuple[str, tuple]] = []
        self._responses = list(responses or [])
        self.committed = 0
        self.rolled_back = 0

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self._responses:
            return self._responses.pop(0)
        return _Cur(None)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


# ─── claim_terminal_notification (the double-send guard) ─────────────────────


def test_claim_returns_true_when_row_returned():
    db = _RecordingDb(responses=[_Cur(row={"id": 7})])
    assert pn.claim_terminal_notification(db, user_id=1, plan_version_id=7) is True
    assert db.committed == 1


def test_claim_returns_false_when_no_row():
    # A racing pass (or an already-notified row) matches 0 rows → no win.
    db = _RecordingDb(responses=[_Cur(row=None)])
    assert pn.claim_terminal_notification(db, user_id=1, plan_version_id=7) is False


def test_claim_sql_is_atomic_and_guarded():
    db = _RecordingDb(responses=[_Cur(row={"id": 7})])
    pn.claim_terminal_notification(db, user_id=3, plan_version_id=9)
    sql, params = db.calls[0]
    # Single conditional UPDATE: flips NULL→NOW only on a terminal row, scoped to
    # (id, user_id), and RETURNING makes the win observable.
    assert "UPDATE plan_versions SET notified_at = NOW()" in sql
    assert "notified_at IS NULL" in sql
    assert "generation_status IN ('ready', 'failed')" in sql
    assert "WHERE id = ? AND user_id = ?" in sql
    assert "RETURNING id" in sql
    assert params == (9, 3)


# ─── build_notification_email ────────────────────────────────────────────────


def test_build_ready_email_has_subject_link_and_greeting():
    subject, text, html = pn.build_notification_email(
        "ready", "Pocket Gopher 2026 — 16-week build", "Andy",
        "https://app/plans/v2/7", None,
    )
    assert "is ready" in subject and "Pocket Gopher" in subject
    assert "Andy" in text and "Andy" in html          # personalized greeting
    assert "Pocket Gopher" in html                     # plan name in the body
    assert "https://app/plans/v2/7" in text
    assert 'href="https://app/plans/v2/7"' in html
    assert "View your plan" in html


def test_build_failed_email_includes_error_and_retry():
    subject, text, html = pn.build_notification_email(
        "failed", "Training plan", "Andy",
        "https://app/plans/v2/new", "Plan synthesis failed (schema_violation).",
    )
    assert "couldn't generate" in subject.lower() or "couldn" in subject
    assert "Plan synthesis failed (schema_violation)." in text
    assert "Plan synthesis failed (schema_violation)." in html
    assert "Try again" in html


def test_build_email_falls_back_to_base_url_without_plan_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.aidstation.pro")
    subject, text, html = pn.build_notification_email(
        "ready", "Training plan", "", None, None,
    )
    # The shared shell always renders a CTA; with no plan URL the button targets
    # the app origin so it still goes somewhere sensible.
    assert "View your plan" in html
    assert 'href="https://app.aidstation.pro"' in html
    assert "https://app.aidstation.pro" in text


# ─── notify_plan_terminal (orchestration + best-effort posture) ──────────────


def _user_row(email="andy@example.com", display_name="Andy", username="andy"):
    return _FakeRow(email=email, display_name=display_name, username=username)


def test_notify_sends_when_claim_won(monkeypatch):
    sent = []
    monkeypatch.setattr(pn, "send_email",
                        lambda *a, **k: sent.append((a, k)) or True)
    monkeypatch.setattr(pn, "target_race_name", lambda db, uid: "Pocket Gopher 2026")
    monkeypatch.setattr(pn, "_plan_url", lambda pvid, status: "https://app/p/7")

    db = _RecordingDb(responses=[
        _Cur(row={"id": 7}),       # claim wins
        _Cur(row=_user_row()),     # user lookup
    ])
    out = pn.notify_plan_terminal(
        db, 1, 7,
        {"generation_status": "ready", "scope_start_date": None,
         "scope_end_date": None, "generation_error": None},
    )
    assert out is True
    assert len(sent) == 1
    (to, subject, text, html), _ = sent[0]
    assert to == "andy@example.com"
    assert "ready" in subject


def test_notify_noop_when_claim_lost(monkeypatch):
    """A racing pass that loses the atomic claim must NOT send (the guard)."""
    sent = []
    monkeypatch.setattr(pn, "send_email", lambda *a, **k: sent.append(a))
    db = _RecordingDb(responses=[_Cur(row=None)])  # claim lost
    out = pn.notify_plan_terminal(
        db, 1, 7, {"generation_status": "ready"},
    )
    assert out is False
    assert sent == []


def test_notify_skips_non_terminal_status(monkeypatch):
    sent = []
    monkeypatch.setattr(pn, "send_email", lambda *a, **k: sent.append(a))
    db = _RecordingDb()
    out = pn.notify_plan_terminal(db, 1, 7, {"generation_status": "generating"})
    assert out is False
    assert sent == []
    # Never even attempted the claim.
    assert db.calls == []


def test_notify_badge_armed_but_no_email_without_address(monkeypatch):
    """Claim won → badge armed; a user with no email gets in-app only (returns
    True, but no send)."""
    sent = []
    monkeypatch.setattr(pn, "send_email", lambda *a, **k: sent.append(a))
    db = _RecordingDb(responses=[
        _Cur(row={"id": 7}),                      # claim wins
        _Cur(row=_user_row(email=None)),          # no email on file
    ])
    out = pn.notify_plan_terminal(db, 1, 7, {"generation_status": "ready"})
    assert out is True
    assert sent == []


def test_notify_swallows_faults(monkeypatch, capsys):
    """A fault anywhere in delivery must NEVER propagate (the plan is already
    terminal + durable); it rolls back and logs."""
    monkeypatch.setattr(pn, "send_email",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    db = _RecordingDb(responses=[
        _Cur(row={"id": 7}),       # claim wins
        _Cur(row=_user_row()),     # user lookup
    ])
    out = pn.notify_plan_terminal(db, 1, 7, {"generation_status": "ready"})
    assert out is False
    assert db.rolled_back == 1
    assert "non-fatal notification failure" in capsys.readouterr().out


# ─── get_unseen_plan_notifications (the badge feed) ──────────────────────────


def test_unseen_empty_when_no_user():
    assert pn.get_unseen_plan_notifications(_RecordingDb(), 0) == []


def test_unseen_decorates_ready_and_failed(monkeypatch):
    monkeypatch.setattr(pn, "target_race_name", lambda db, uid: "Pocket Gopher 2026")
    rows = [
        _FakeRow(id=7, generation_status="ready", generation_error=None,
                 scope_start_date=None, scope_end_date=None),
        _FakeRow(id=8, generation_status="failed",
                 generation_error="Plan synthesis failed (x).",
                 scope_start_date=None, scope_end_date=None),
    ]
    db = _RecordingDb(responses=[_Cur(rows=rows)])
    out = pn.get_unseen_plan_notifications(db, 42)
    assert [n["id"] for n in out] == [7, 8]
    assert out[0]["status"] == "ready" and out[0]["category"] == "good"
    assert out[0]["error"] is None
    assert out[1]["status"] == "failed" and out[1]["category"] == "bad"
    assert out[1]["error"] == "Plan synthesis failed (x)."


def test_unseen_query_is_scoped_and_gated():
    db = _RecordingDb(responses=[_Cur(rows=[])])
    pn.get_unseen_plan_notifications(db, 42)
    sql, params = db.calls[0]
    assert "WHERE user_id = ?" in sql
    assert "notified_at IS NOT NULL" in sql           # legacy ready rows excluded
    assert "notification_seen_at IS NULL" in sql       # undismissed only
    assert "generation_status IN ('ready', 'failed')" in sql
    assert params == (42,)


# ─── mark_plan_notification_seen (dismiss) ───────────────────────────────────


def test_mark_seen_is_scoped_and_idempotent():
    db = _RecordingDb()
    pn.mark_plan_notification_seen(db, user_id=3, plan_version_id=9)
    sql, params = db.calls[0]
    assert "SET notification_seen_at = NOW()" in sql
    assert "WHERE id = ? AND user_id = ?" in sql
    assert "notification_seen_at IS NULL" in sql  # idempotent: only unstamped
    assert params == (9, 3)
    assert db.committed == 1
