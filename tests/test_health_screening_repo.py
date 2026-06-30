"""Tests for `health_screening_repo` — the Health Screening Spec v2 capture.

Uses a minimal `_FakeConn` (records `execute` calls + serves queued rows) in the
style of `tests/test_plan_nutrition_repo.py`. Guards the two behaviours the spec
is strict about: the sensitive free-text opt-in gate (§7.2 — no details stored
without opt-in) and the flag taxonomy (§4/§5).
"""

from __future__ import annotations

import json

import health_screening_repo as hs


# ─── fakes ───────────────────────────────────────────────────────────────────


class _FakeCursor:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list = []
        self.commits = 0

    def queue(self, row=None):
        self.responses.append(row)

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        row = self.responses.pop(0) if self.responses else None
        return _FakeCursor(row=row)

    def commit(self):
        self.commits += 1


def _form(**kw):
    return dict(kw)


# ─── taxonomy invariants ─────────────────────────────────────────────────────


def test_every_question_code_has_a_label():
    for q in hs.QUESTIONS:
        assert q["code"] in hs.FLAG_LABELS
    assert len(hs.QUESTIONS) == 10
    # question numbers are 1..10 contiguous
    assert [q["num"] for q in hs.QUESTIONS] == list(range(1, 11))


def test_pregnancy_flag_is_a_real_question_code():
    assert hs.PREGNANCY_FLAG in {q["code"] for q in hs.QUESTIONS}


# ─── parse_answers ───────────────────────────────────────────────────────────


def test_parse_all_no():
    flags, details, optin = hs.parse_answers(_form(**{f"q{i}": "no" for i in range(1, 11)}))
    assert flags == []
    assert details == {}
    assert optin is False


def test_parse_flags_in_question_order():
    flags, _, _ = hs.parse_answers(_form(q3="yes", q1="yes", q8="yes"))
    # ordered by QUESTIONS, not by form insertion
    assert flags == ["CARDIO_CHEST_PAIN", "CARDIO_CONDITION", "PREGNANCY"]


def test_details_suppressed_without_optin():
    flags, details, optin = hs.parse_answers(
        _form(q3="yes", detail_CARDIO_CONDITION="afib since 2019")
    )
    assert flags == ["CARDIO_CONDITION"]
    assert details == {}  # §7.2 — no opt-in, no free text stored
    assert optin is False


def test_details_kept_with_optin_for_flagged_only():
    flags, details, optin = hs.parse_answers(
        _form(
            q3="yes",
            detail_CARDIO_CONDITION="afib since 2019",
            detail_MSK_CONDITION="knee — but I answered no",  # not flagged → ignored
            details_optin="on",
        )
    )
    assert flags == ["CARDIO_CONDITION"]
    assert details == {"CARDIO_CONDITION": "afib since 2019"}
    assert optin is True


def test_optin_truthy_variants():
    for v in ("on", "1", "true", "TRUE"):
        _, _, optin = hs.parse_answers(_form(q1="yes", details_optin=v))
        assert optin is True


def test_blank_detail_not_stored_even_with_optin():
    _, details, _ = hs.parse_answers(
        _form(q1="yes", detail_CARDIO_CHEST_PAIN="   ", details_optin="on")
    )
    assert details == {}


# ─── flag_descriptions ───────────────────────────────────────────────────────


def test_flag_descriptions_order_and_unknown_skipped():
    out = hs.flag_descriptions(["PREGNANCY", "NOPE", "MSK_CONDITION"])
    assert out == [hs.FLAG_LABELS["PREGNANCY"], hs.FLAG_LABELS["MSK_CONDITION"]]


# ─── save_screening ──────────────────────────────────────────────────────────


def test_save_writes_acknowledged_upsert_with_json_flags():
    db = _FakeConn()
    hs.save_screening(db, 42, flags=["PREGNANCY"], details={"PREGNANCY": "due in May"},
                      details_optin=True)
    assert len(db.calls) == 1
    sql, params = db.calls[0]
    assert "INSERT INTO health_screening" in sql
    assert "ON CONFLICT (user_id) DO UPDATE" in sql
    assert "NOW() + INTERVAL '365 days'" in sql  # §9.1 cadence
    user_id, version, flags_json, details_json, optin = params
    assert user_id == 42
    assert version == hs.SCREENING_VERSION
    assert json.loads(flags_json) == ["PREGNANCY"]
    assert json.loads(details_json) == {"PREGNANCY": "due in May"}
    assert optin is True


def test_save_suppresses_details_when_optin_off():
    db = _FakeConn()
    hs.save_screening(db, 7, flags=["CARDIO_CONDITION"],
                      details={"CARDIO_CONDITION": "should not persist"},
                      details_optin=False)
    _, params = db.calls[0]
    _, _, flags_json, details_json, optin = params
    assert json.loads(flags_json) == ["CARDIO_CONDITION"]
    assert json.loads(details_json) == {}  # §7.2 enforced at the write boundary
    assert optin is False


# ─── get_screening ───────────────────────────────────────────────────────────


def test_get_returns_none_for_no_user():
    assert hs.get_screening(_FakeConn(), None) is None


def test_get_filters_on_acknowledged_and_returns_dict():
    db = _FakeConn()
    db.queue({
        "user_id": 42, "screening_version": "v1", "flags": ["PREGNANCY"],
        "details": {}, "details_optin": False, "acknowledged": True,
        "acknowledged_at": None, "last_assessed_at": None,
        "reassessment_due_at": None, "reassessment_overdue": False,
    })
    out = hs.get_screening(db, 42)
    assert out["flags"] == ["PREGNANCY"]
    sql, params = db.calls[0]
    assert "acknowledged = TRUE" in sql
    assert params == (42,)
