"""Tests for the Layer 3D HITL gate wiring (#213, Slice 1):

- `plan_sessions_repo` gate persistence (save/load/prior-resolutions round-trip)
- the advance-loop parking path (`_advance_plan_generation`): a non-green gate
  raises `Layer3DGateBlocked` in the orchestrator → the row parks at
  `needs_review` (NOT failed); a `needs_review` row short-circuits the poller/cron
- the review-screen routes (`plan_review`, `resolve_review_item`,
  `generate_from_review`) + one-in-flight enforcement in `new_plan`

Pure helpers + Flask test-client routes against fake DB connections (same
pattern as `tests/test_routes_plan_create.py`). No LLM, no real DB.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from types import SimpleNamespace

from flask import Blueprint, Flask

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-layer3d-wiring")

import plan_sessions_repo
import routes.plan_create as plan_create
from layer3d.gate import GateItem, GateResolution, Layer3DGate, Layer3DGateBlocked
from routes.plan_create import bp as plan_create_bp


# ─── Fakes ──────────────────────────────────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return _FakeRow(self._row) if self._row is not None else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _GateConn:
    """Stateful fake that round-trips the `hitl_gate` JSONB column and serves a
    canned plan_versions row for `_load_plan_version`. SQL-pattern matched so the
    route call order doesn't matter."""

    def __init__(self, plan_row=None, hitl_gate_json=None, in_flight_row=None):
        self.plan_row = plan_row
        self.hitl_gate_json = hitl_gate_json
        self.in_flight_row = in_flight_row
        self.calls: list[tuple[str, tuple]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        s = " ".join(sql.split())
        if s.startswith("UPDATE plan_versions SET hitl_gate"):
            self.hitl_gate_json = params[0]
            return _FakeCursor()
        if "SELECT hitl_gate FROM plan_versions" in s:
            return _FakeCursor(row={"hitl_gate": self.hitl_gate_json})
        if s.startswith("SELECT id, generation_status FROM plan_versions"):
            return _FakeCursor(row=self.in_flight_row)
        if s.startswith("SELECT id, user_id, created_at"):
            return _FakeCursor(row=self.plan_row)
        if s.startswith("UPDATE plan_versions SET generation_status"):
            if self.plan_row is not None and "needs_review" in s:
                self.plan_row["generation_status"] = "needs_review"
            elif self.plan_row is not None and "generating" in s:
                self.plan_row["generation_status"] = "generating"
            return _FakeCursor()
        return _FakeCursor()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _gate(status="needs_review", items=None, input_fingerprint=None):
    return Layer3DGate(
        user_id=3,
        plan_version_id=7,
        gate_status=status,
        items=items if items is not None else [],
        evaluated_against={"0A": "v7"},
        input_fingerprint=input_fingerprint,
    )


def _warning_item(item_key="k1", acknowledged=False):
    res = (
        GateResolution(kind="acknowledged", resolved_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
        if acknowledged
        else None
    )
    return GateItem(
        item_key=item_key,
        source="3B",
        source_item_id="first_time_competitive_goal",
        severity="warning",
        title="First Time Competitive Goal",
        message="This is your first competitive event at this distance.",
        resolution_options=["Acknowledge the risk"],
        revise_target="h2.goal_outcome",
        can_acknowledge=True,
        evidence={},
        status="acknowledged" if acknowledged else "pending",
        resolution=res,
    )


def _blocker_item(item_key="b1"):
    return GateItem(
        item_key=item_key,
        source="2D",
        source_item_id="post_surgical_clearance",
        severity="blocker",
        title="Post Surgical Clearance",
        message="Get clearance before high-load training.",
        resolution_options=["Confirm clearance"],
        revise_target="profile.injuries",
        can_acknowledge=False,
        evidence={},
    )


def _plan_row(status="needs_review", pvid=7, uid=3):
    return {
        "id": pvid, "user_id": uid, "created_at": "ts", "created_via": "plan_create",
        "scope_start_date": date(2026, 6, 1), "scope_end_date": date(2026, 7, 17),
        "pattern": "A", "generation_status": status, "generation_error": None,
        "generation_units_cached": 0, "generation_stall_passes": 0,
        "completed_at": None, "archived_at": None, "refresh_nl_text": None,
        "refresh_parent_version_id": None, "refresh_triggered_by_ad_hoc_id": None,
        "refresh_cap_overridden": False, "refresh_parsed_intent_json": None,
        "refresh_used_degraded": False,
    }


# ─── Repo accessors ──────────────────────────────────────────────────────────


class TestGatePersistence:
    def test_save_then_load_roundtrip(self):
        conn = _GateConn()
        gate = _gate(items=[_warning_item()])
        plan_sessions_repo.save_hitl_gate(conn, 3, 7, gate)
        loaded = plan_sessions_repo.load_hitl_gate(conn, 3, 7)
        assert loaded is not None
        assert loaded.gate_status == "needs_review"
        assert loaded.items[0].item_key == "k1"
        # save stamps evaluated_at when the pure function left it None (§6.1).
        assert loaded.evaluated_at is not None

    def test_save_writes_user_scoped_update(self):
        conn = _GateConn()
        plan_sessions_repo.save_hitl_gate(conn, 3, 7, _gate())
        sql, params = conn.calls[-1]
        assert "UPDATE plan_versions SET hitl_gate" in sql
        assert "WHERE id = ? AND user_id = ?" in sql
        assert params[1:] == (7, 3)

    def test_load_null_column_returns_none(self):
        conn = _GateConn(hitl_gate_json=None)
        assert plan_sessions_repo.load_hitl_gate(conn, 3, 7) is None

    def test_prior_resolutions_extracts_resolved_items_only(self):
        conn = _GateConn()
        gate = _gate(items=[_warning_item("k1", acknowledged=True), _warning_item("k2")])
        plan_sessions_repo.save_hitl_gate(conn, 3, 7, gate)
        prior = plan_sessions_repo.load_prior_resolutions(conn, 3, 7)
        assert set(prior) == {"k1"}
        assert prior["k1"].kind == "acknowledged"

    def test_prior_resolutions_empty_when_no_gate(self):
        conn = _GateConn(hitl_gate_json=None)
        assert plan_sessions_repo.load_prior_resolutions(conn, 3, 7) == {}


# ─── Advance loop parking + short-circuit ────────────────────────────────────


class _QueueConn:
    """Queue-based fake (mirrors test_routes_plan_create) for the advance loop."""

    def __init__(self):
        self.calls = []
        self.commits = 0
        self.rollbacks = 0
        self._responses = []

    def queue(self, row=None, rows=None):
        self._responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        row, rows = (self._responses.pop(0) if self._responses else (None, []))
        return _FakeCursor(row=row, rows=rows)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _queue_plan_for_advance(conn, status="generating", pvid=7, uid=3):
    conn.queue(row=_plan_row(status=status, pvid=pvid, uid=uid))
    conn.queue(row={"id": pvid})  # advance-lock claim won


class TestAdvanceLoopGate:
    def test_needs_review_short_circuits_without_cone(self, monkeypatch):
        conn = _QueueConn()
        conn.queue(row=_plan_row(status="needs_review"))

        def _boom(*a, **k):
            raise AssertionError("cone must not run for a needs_review row")

        monkeypatch.setattr(plan_create, "orchestrate_plan_create", _boom)
        out = plan_create._advance_plan_generation(conn, 3, 7)
        assert out == {"status": "needs_review"}
        assert conn.commits == 0  # no writes on the short-circuit

    def test_gate_blocked_parks_at_needs_review(self, monkeypatch):
        conn = _QueueConn()
        _queue_plan_for_advance(conn, status="generating")

        def _raise_blocked(*a, **k):
            raise Layer3DGateBlocked(_gate("blocked", items=[_blocker_item()]))

        monkeypatch.setattr(plan_create, "orchestrate_plan_create", _raise_blocked)
        monkeypatch.setattr(plan_create, "_build_layer4_cache", lambda: "CACHE")

        def _persist_must_not_run(*a, **k):
            raise AssertionError("must not persist sessions on a parked plan")

        monkeypatch.setattr(plan_create, "persist_layer4_sessions", _persist_must_not_run)
        out = plan_create._advance_plan_generation(conn, 3, 7)
        assert out == {"status": "needs_review"}
        # Flipped to needs_review (NOT failed); no DELETE/ready writes.
        assert any("generation_status = 'needs_review'" in c[0] for c in conn.calls)
        assert not any("generation_status = 'failed'" in c[0] for c in conn.calls)
        assert not any("DELETE FROM plan_sessions" in c[0] for c in conn.calls)


# ─── Review routes ───────────────────────────────────────────────────────────


def _review_app():
    """Minimal app: the real plan_create + plans blueprints, the repo's real
    `templates/` on the loader, but a STUB `base.html` (so review.html renders
    without booting the whole app / its DB-connecting import). CSRF is not
    registered, so POSTs need no token."""
    import os as _os

    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

    from routes.plans import bp as plans_bp

    templates_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "templates")
    app = Flask(__name__)
    app.secret_key = "test"
    app.jinja_loader = ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(templates_dir),
    ])
    app.register_blueprint(plan_create_bp)
    app.register_blueprint(plans_bp)
    app.jinja_env.globals.setdefault("csrf_token", lambda: "tok")
    return app


class TestReviewRoutes:
    def _client(self, monkeypatch, conn):
        monkeypatch.setattr(plan_create, "get_db", lambda: conn)
        monkeypatch.setattr(plan_create, "current_user_id", lambda: 3)
        return _review_app().test_client()

    def test_review_get_renders_items(self, monkeypatch):
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(conn, 3, 7, _gate(items=[_warning_item(), _blocker_item()]))
        client = self._client(monkeypatch, conn)
        resp = client.get("/plans/v2/7/review")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "First Time Competitive Goal" in body
        assert "Post Surgical Clearance" in body
        # The blocker is revise-only — no Acknowledge control for it.
        assert "Fix via: profile.injuries" in body

    def test_review_get_ready_redirects(self, monkeypatch):
        conn = _GateConn(plan_row=_plan_row("ready"))
        client = self._client(monkeypatch, conn)
        resp = client.get("/plans/v2/7/review")
        assert resp.status_code == 302

    def test_acknowledge_warning_recomputes_green(self, monkeypatch):
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(conn, 3, 7, _gate(items=[_warning_item("k1")]))
        client = self._client(monkeypatch, conn)
        resp = client.post(
            "/plans/v2/7/review/resolve",
            data={"item_key": "k1", "reasoning": "I accept the risk"},
        )
        assert resp.status_code == 302
        reloaded = plan_sessions_repo.load_hitl_gate(conn, 3, 7)
        assert reloaded.gate_status == "green"
        assert reloaded.items[0].status == "acknowledged"
        assert reloaded.items[0].resolution.reasoning == "I accept the risk"

    def test_acknowledge_blocker_rejected(self, monkeypatch):
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(conn, 3, 7, _gate("blocked", items=[_blocker_item("b1")]))
        client = self._client(monkeypatch, conn)
        resp = client.post("/plans/v2/7/review/resolve", data={"item_key": "b1"})
        assert resp.status_code == 302
        reloaded = plan_sessions_repo.load_hitl_gate(conn, 3, 7)
        # Still blocked; the blocker was not acknowledged.
        assert reloaded.gate_status == "blocked"
        assert reloaded.items[0].resolution is None

    def test_generate_from_review_refused_when_not_green(self, monkeypatch):
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(conn, 3, 7, _gate("blocked", items=[_blocker_item()]))
        client = self._client(monkeypatch, conn)
        resp = client.post("/plans/v2/7/review/generate")
        assert resp.status_code == 302
        assert "/review" in resp.headers["Location"]
        assert not any("generation_status = 'generating'" in c[0] for c in conn.calls)

    def test_generate_from_review_proceeds_when_green(self, monkeypatch):
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(
            conn, 3, 7, _gate("green", items=[_warning_item("k1", acknowledged=True)])
        )
        client = self._client(monkeypatch, conn)
        resp = client.post("/plans/v2/7/review/generate")
        assert resp.status_code == 302
        assert "/progress" in resp.headers["Location"]
        assert any("generation_status = 'generating'" in c[0] for c in conn.calls)


# ─── Reading-B staleness re-check (#213) ─────────────────────────────────────


class TestGateStaleness:
    """A parked gate carries an `input_fingerprint`; the review routes recompute
    it on re-entry / [Generate] and re-evaluate against current reality when the
    athlete's inputs changed. `compute_gate_input_fingerprint` +
    `load_target_race_event_payload` are stubbed so no DB / LLM runs — the digest
    value alone drives the stale/fresh decision."""

    def _client(self, monkeypatch, conn, *, current_fingerprint):
        monkeypatch.setattr(plan_create, "get_db", lambda: conn)
        monkeypatch.setattr(plan_create, "current_user_id", lambda: 3)
        monkeypatch.setattr(
            plan_create, "load_target_race_event_payload", lambda *a, **k: None
        )
        monkeypatch.setattr(
            plan_create,
            "compute_gate_input_fingerprint",
            lambda *a, **k: current_fingerprint,
        )
        return _review_app().test_client()

    def test_review_rekicks_when_inputs_changed(self, monkeypatch):
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(
            conn, 3, 7, _gate(items=[_warning_item()], input_fingerprint="OLD")
        )
        client = self._client(monkeypatch, conn, current_fingerprint="NEW")
        resp = client.get("/plans/v2/7/review")
        # Stale → flip to generating + redirect to the progress poller (which
        # re-runs the pipeline + re-evaluates the gate against current inputs).
        assert resp.status_code == 302
        assert "/progress" in resp.headers["Location"]
        assert any("generation_status = 'generating'" in c[0] for c in conn.calls)

    def test_review_renders_when_inputs_unchanged(self, monkeypatch):
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(
            conn, 3, 7, _gate(items=[_warning_item()], input_fingerprint="SAME")
        )
        client = self._client(monkeypatch, conn, current_fingerprint="SAME")
        resp = client.get("/plans/v2/7/review")
        assert resp.status_code == 200
        assert not any(
            "generation_status = 'generating'" in c[0] for c in conn.calls
        )

    def test_review_renders_when_no_baseline_fingerprint(self, monkeypatch):
        # A gate parked before this shipped (no input_fingerprint) is treated as
        # fresh — the staleness probe is never even invoked.
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(conn, 3, 7, _gate(items=[_warning_item()]))

        def _must_not_probe(*a, **k):
            raise AssertionError("staleness probe ran without a baseline fingerprint")

        monkeypatch.setattr(plan_create, "compute_gate_input_fingerprint", _must_not_probe)
        monkeypatch.setattr(plan_create, "get_db", lambda: conn)
        monkeypatch.setattr(plan_create, "current_user_id", lambda: 3)
        resp = _review_app().test_client().get("/plans/v2/7/review")
        assert resp.status_code == 200

    def test_generate_rekicks_when_inputs_changed_even_if_not_green(self, monkeypatch):
        # Stale + stored verdict still 'blocked' (e.g. the athlete's edit cleared
        # the blocker) → don't trust the stale verdict; flip to generating and let
        # the resumed orchestrator re-gate against current reality.
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(
            conn, 3, 7, _gate("blocked", items=[_blocker_item()], input_fingerprint="OLD")
        )
        client = self._client(monkeypatch, conn, current_fingerprint="NEW")
        resp = client.post("/plans/v2/7/review/generate")
        assert resp.status_code == 302
        assert "/progress" in resp.headers["Location"]
        assert any("generation_status = 'generating'" in c[0] for c in conn.calls)

    def test_generate_still_guards_when_inputs_unchanged(self, monkeypatch):
        # Fresh + stored verdict 'blocked' → hold the "resolve every item" guard.
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(
            conn, 3, 7, _gate("blocked", items=[_blocker_item()], input_fingerprint="SAME")
        )
        client = self._client(monkeypatch, conn, current_fingerprint="SAME")
        resp = client.post("/plans/v2/7/review/generate")
        assert resp.status_code == 302
        assert "/review" in resp.headers["Location"]
        assert not any(
            "generation_status = 'generating'" in c[0] for c in conn.calls
        )

    def test_resolve_bounces_to_review_when_inputs_changed(self, monkeypatch):
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        plan_sessions_repo.save_hitl_gate(
            conn, 3, 7, _gate(items=[_warning_item("k1")], input_fingerprint="OLD")
        )
        client = self._client(monkeypatch, conn, current_fingerprint="NEW")
        resp = client.post(
            "/plans/v2/7/review/resolve",
            data={"item_key": "k1", "reasoning": "stale ack"},
        )
        assert resp.status_code == 302
        assert "/review" in resp.headers["Location"]
        # No acknowledgment was recorded against the stale finding.
        reloaded = plan_sessions_repo.load_hitl_gate(conn, 3, 7)
        assert reloaded.items[0].resolution is None


# ─── [Fix this] revise links (#213) ──────────────────────────────────────────


def _revise_item(item_key, revise_target, *, severity="warning", source="2A"):
    """A gate item carrying an arbitrary `revise_target`, for the link mapping."""
    return GateItem(
        item_key=item_key,
        source=source,
        source_item_id=item_key,
        severity=severity,
        title=item_key,
        message="msg",
        resolution_options=[],
        revise_target=revise_target,
        can_acknowledge=severity != "blocker",
        evidence={},
    )


def _revise_surfaces_app():
    """A bare app that registers the real revise-target endpoint NAMES (with
    throwaway view funcs) so `url_for` in `_build_revise_urls` resolves them
    without importing the heavy `routes.injuries`/`profile`/`race_events`
    modules."""
    app = Flask(__name__)
    specs = [
        ("injuries", "/injuries", "list_entries", lambda: ""),
        ("profile", "/profile/", "edit", lambda: ""),
        (
            "race_events",
            "/profile/race-events/<int:race_event_id>/edit",
            "edit_race",
            lambda race_event_id: "",
        ),
    ]
    for name, rule, endpoint, view in specs:
        sub = Blueprint(name, __name__)
        sub.add_url_rule(rule, endpoint, view)
        app.register_blueprint(sub)
    return app


class TestReviseUrls:
    """`_build_revise_urls` maps each item's `revise_target` to its edit surface
    (the [Fix this] links), and degrades to "no link" — never an error — when a
    surface can't be resolved."""

    def _items(self):
        return [
            _blocker_item("b1"),                            # profile.injuries
            _revise_item("d1", "profile.disciplines"),
            _revise_item("n1", "profile.nutrition"),
            _revise_item("a1", "profile.availability"),
            _warning_item("h1"),                            # h2.goal_outcome
            _revise_item("p1", "h3.plan_duration_weeks"),   # no edit surface
        ]

    def test_maps_every_known_target(self, monkeypatch):
        monkeypatch.setattr(
            plan_create,
            "load_target_race_event_payload",
            lambda db, uid: SimpleNamespace(race_event_id=42),
        )
        gate = _gate(items=self._items())
        with _revise_surfaces_app().test_request_context():
            urls = plan_create._build_revise_urls(object(), 3, gate)
        assert urls["profile.injuries"] == "/injuries"
        # disciplines / nutrition / availability all edit on the profile page.
        assert urls["profile.disciplines"] == "/profile/"
        assert urls["profile.nutrition"] == "/profile/"
        assert urls["profile.availability"] == "/profile/"
        assert urls["h2.goal_outcome"] == "/profile/race-events/42/edit"
        # 3B h3.* (open-ended plan duration) has no athlete edit surface → no link.
        assert "h3.plan_duration_weeks" not in urls

    def test_no_target_race_drops_only_h2_links(self, monkeypatch):
        monkeypatch.setattr(
            plan_create, "load_target_race_event_payload", lambda db, uid: None
        )
        gate = _gate(items=self._items())
        with _revise_surfaces_app().test_request_context():
            urls = plan_create._build_revise_urls(object(), 3, gate)
        assert "h2.goal_outcome" not in urls
        # The race-independent surfaces still resolve.
        assert urls["profile.injuries"] == "/injuries"
        assert urls["profile.disciplines"] == "/profile/"

    def test_unregistered_surfaces_yield_empty_map(self, monkeypatch):
        # No revise endpoints registered → BuildError on every url_for → empty
        # map, never a 500.
        monkeypatch.setattr(
            plan_create,
            "load_target_race_event_payload",
            lambda db, uid: SimpleNamespace(race_event_id=42),
        )
        gate = _gate(items=self._items())
        with Flask(__name__).test_request_context():
            urls = plan_create._build_revise_urls(object(), 3, gate)
        assert urls == {}

    def test_race_lookup_error_is_swallowed(self, monkeypatch):
        # A DB error resolving the target race must not bubble out of the review
        # render — the h2.* link just drops, everything else still resolves.
        def _boom(db, uid):
            raise RuntimeError("db down")

        monkeypatch.setattr(plan_create, "load_target_race_event_payload", _boom)
        gate = _gate(items=self._items())
        with _revise_surfaces_app().test_request_context():
            urls = plan_create._build_revise_urls(object(), 3, gate)
        assert "h2.goal_outcome" not in urls
        assert urls["profile.injuries"] == "/injuries"
        assert urls["profile.disciplines"] == "/profile/"

    def test_no_targets_returns_empty(self):
        gate = _gate(items=[])
        with _revise_surfaces_app().test_request_context():
            assert plan_create._build_revise_urls(object(), 3, gate) == {}


class TestReviseLinkRender:
    """The review screen renders a real [Fix this] link for a mapped target."""

    def _app(self):
        app = _review_app()
        for name, rule, endpoint, view in [
            ("injuries", "/injuries", "list_entries", lambda: ""),
        ]:
            sub = Blueprint(name, __name__)
            sub.add_url_rule(rule, endpoint, view)
            app.register_blueprint(sub)
        return app

    def test_blocker_renders_fix_this_link(self, monkeypatch):
        conn = _GateConn(plan_row=_plan_row("needs_review"))
        # A single blocker → profile.injuries (needs no locale/race lookup).
        plan_sessions_repo.save_hitl_gate(conn, 3, 7, _gate("blocked", items=[_blocker_item()]))
        monkeypatch.setattr(plan_create, "get_db", lambda: conn)
        monkeypatch.setattr(plan_create, "current_user_id", lambda: 3)
        resp = self._app().test_client().get("/plans/v2/7/review")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'href="/injuries"' in body
        assert "Fix this" in body
        # The plain-text stub is gone once the target resolves to a link.
        assert "Fix via: profile.injuries" not in body


# ─── One-in-flight enforcement ───────────────────────────────────────────────


class TestOneInFlight:
    def _client(self, monkeypatch, conn):
        monkeypatch.setattr(plan_create, "get_db", lambda: conn)
        monkeypatch.setattr(plan_create, "current_user_id", lambda: 3)
        return _review_app().test_client()

    def test_new_plan_refused_when_one_needs_review(self, monkeypatch):
        conn = _GateConn(
            in_flight_row={"id": 9, "generation_status": "needs_review"}
        )
        client = self._client(monkeypatch, conn)
        resp = client.post("/plans/v2/new", data={"plan_start_date": "2999-01-01"})
        assert resp.status_code == 302
        assert "/9/review" in resp.headers["Location"]

    def test_new_plan_refused_when_one_generating(self, monkeypatch):
        conn = _GateConn(
            in_flight_row={"id": 9, "generation_status": "generating"}
        )
        client = self._client(monkeypatch, conn)
        resp = client.post("/plans/v2/new", data={"plan_start_date": "2999-01-01"})
        assert resp.status_code == 302
        assert "/9/progress" in resp.headers["Location"]
