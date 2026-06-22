"""webhook_events housekeeping tests (#250) — dead-letter sweep + 90-day prune
and the Bearer-CRON_SECRET cron gate. No real DB: a fake records the SQL issued
and returns controllable RETURNING rows.
"""
from __future__ import annotations

from flask import Flask


class _Cur:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return self._rows

    def fetchone(self):  # pragma: no cover - unused here
        return self._rows[0] if self._rows else None


class _MaintDB:
    def __init__(self, dead_ids=(), prune_ids=()):
        self._dead = [{'id': i} for i in dead_ids]
        self._prune = [{'id': i} for i in prune_ids]
        self.sql: list[str] = []
        self.committed = False
        self.rolled_back = False

    def execute(self, sql, params=()):
        self.sql.append(sql)
        stripped = sql.lstrip()
        if stripped.startswith('UPDATE webhook_events'):
            return _Cur(self._dead)
        if stripped.startswith('DELETE FROM webhook_events'):
            return _Cur(self._prune)
        return _Cur()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


# ── run_maintenance ───────────────────────────────────────────────────

class TestRunMaintenance:
    def test_counts_and_commit(self):
        from routes.webhook_maintenance import run_maintenance
        db = _MaintDB(dead_ids=(1, 2), prune_ids=(3, 4, 5))
        dead, pruned = run_maintenance(db)
        assert (dead, pruned) == (2, 3)
        assert db.committed is True

    def test_sweep_runs_before_prune(self):
        from routes.webhook_maintenance import run_maintenance
        db = _MaintDB()
        run_maintenance(db)
        update_idx = next(i for i, s in enumerate(db.sql) if s.lstrip().startswith('UPDATE'))
        delete_idx = next(i for i, s in enumerate(db.sql) if s.lstrip().startswith('DELETE'))
        assert update_idx < delete_idx

    def test_dead_letter_targets_only_aged_failures(self):
        from routes.webhook_maintenance import run_maintenance
        db = _MaintDB()
        run_maintenance(db)
        update_sql = next(s for s in db.sql if s.lstrip().startswith('UPDATE'))
        # only failed (error set), still-unprocessed, not already dead-lettered
        assert 'error IS NOT NULL' in update_sql
        assert 'processed_at IS NULL' in update_sql
        assert 'dead_lettered_at IS NULL' in update_sql
        assert "INTERVAL '1 days'" in update_sql

    def test_prune_uses_90_day_retention(self):
        from routes.webhook_maintenance import run_maintenance
        db = _MaintDB()
        run_maintenance(db)
        delete_sql = next(s for s in db.sql if s.lstrip().startswith('DELETE'))
        assert "INTERVAL '90 days'" in delete_sql

    def test_windows_are_configurable(self):
        from routes.webhook_maintenance import run_maintenance
        db = _MaintDB()
        run_maintenance(db, dead_letter_after_days=3, retain_days=30)
        assert any("INTERVAL '3 days'" in s for s in db.sql)
        assert any("INTERVAL '30 days'" in s for s in db.sql)


# ── cron route ────────────────────────────────────────────────────────

def _app():
    app = Flask(__name__)
    import routes.webhook_maintenance as wm
    app.register_blueprint(wm.bp)
    return app


class TestCronRoute:
    def test_requires_auth(self, monkeypatch):
        import routes.webhook_maintenance as wm
        monkeypatch.setattr(wm, 'cron_authorized', lambda: False)
        resp = _app().test_client().get('/integrations/webhooks/cron/maintenance')
        assert resp.status_code == 401

    def test_runs_and_returns_counts(self, monkeypatch):
        import routes.webhook_maintenance as wm
        db = _MaintDB(dead_ids=(1,), prune_ids=(2, 3))
        monkeypatch.setattr(wm, 'cron_authorized', lambda: True)
        monkeypatch.setattr(wm, 'get_db', lambda: db)
        resp = _app().test_client().post('/integrations/webhooks/cron/maintenance')
        assert resp.status_code == 200
        assert resp.get_json() == {'dead_lettered': 1, 'pruned': 2}
