"""Tests for the #196 Phase 3 Slice 4 `canonical_cardio_feed` view + the
consumer repoints — Slice 4a "fix the math first" (training-load +
plan-compliance + coaching) and Slice 4b "fix the display next" (the Data-hub
Files list + the dashboard cardio surfaces).

The view itself is raw SQL DDL that auto-applies on each deploy; the container
has no Postgres to execute it against (Neon egress blocked), so — mirroring
Slice 3's "INSERT placeholder/param parity verified by inspection" posture —
these tests verify the view's structure *mechanically* (both UNION ALL branches
expose the same columns positionally, since UNION ALL is positional) and that
the math-path consumers now read the deduped feed rather than raw cardio_log.

The behavioural collapse (N rows → one) lives in the view's SQL and is covered
by a LIVE-VERIFY against prod, not here. These are read as plain source text so
no Flask-app import (which would block on the container's Neon egress) is needed.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text()


def _extract_view_ddl() -> str:
    """The CREATE OR REPLACE VIEW … body, from init_db's _PG_MIGRATIONS."""
    src = _read("init_db.py")
    i = src.index("CREATE OR REPLACE VIEW canonical_cardio_feed")
    end = src.index("cluster_id IS NULL", i) + len("cluster_id IS NULL")
    return src[i:end]


def _split_top_level_commas(select_body: str) -> list[str]:
    """Split a SELECT column list on top-level commas only — commas inside the
    correlated plan_item_id subquery's parens must not count as separators."""
    cols: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in select_body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            cols.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        cols.append(tail)
    return cols


def _branch_columns(ddl: str, *, clustered: bool) -> list[str]:
    if clustered:
        body = ddl[ddl.index("SELECT") + len("SELECT"): ddl.index("FROM canonical_activity ca")]
    else:
        after = ddl[ddl.index("UNION ALL"):]
        body = after[after.index("SELECT") + len("SELECT"): after.index("FROM cardio_log cl")]
    return _split_top_level_commas(body)


class TestCanonicalCardioFeedView:
    def test_view_present_with_both_branches(self):
        ddl = _extract_view_ddl()
        # clustered branch: one row per cluster off the merged canonical record
        assert "FROM canonical_activity ca" in ddl
        assert "JOIN cardio_log cl ON cl.id = ca.primary_cardio_log_id" in ddl
        # unclustered branch: raw rows that were never grouped
        assert "UNION ALL" in ddl
        assert "FROM cardio_log cl" in ddl
        assert "WHERE cl.cluster_id IS NULL" in ddl

    def test_union_branches_have_matching_column_count(self):
        # UNION ALL is positional — the two branches MUST list the same number of
        # columns in the same order or the merged feed silently mis-maps fields.
        ddl = _extract_view_ddl()
        clustered = _branch_columns(ddl, clustered=True)
        unclustered = _branch_columns(ddl, clustered=False)
        assert len(clustered) == len(unclustered), (len(clustered), len(unclustered))
        # 4 identity (date/activity/discipline_id/started_at) + 25 metric +
        # id/user_id/cluster_id/plan_item_id/notes/created_at + 6 provider ids.
        assert len(clustered) == 41

    def test_plan_item_id_pulled_from_any_matched_member(self):
        # A clustered ride's plan_item_id comes from whichever member is
        # plan-matched (not just the primary), so compliance still resolves when
        # the richest copy wasn't the one linked to the plan item.
        ddl = _extract_view_ddl()
        assert "m.cluster_id = ca.cluster_id AND m.plan_item_id IS NOT NULL" in ddl


class TestMathConsumersReadFeed:
    def test_layer3a_load_paths_read_feed(self):
        src = _read("layer3a/integration.py")
        # both training-load reads (recent_workouts + combined_load) repointed
        assert src.count("FROM canonical_cardio_feed") >= 2
        # per-provider coverage stays on raw cardio_log (deliberate)
        assert "FILTER (WHERE garmin_activity_id IS NOT NULL) AS garmin_n" in src

    def test_plans_compliance_joins_feed(self):
        src = _read("routes/plans.py")
        assert "JOIN canonical_cardio_feed cl ON cl.plan_item_id = pi.id" in src
        # the old raw-table compliance join is gone (would double-count)
        assert "JOIN cardio_log cl ON cl.plan_item_id = pi.id" not in src

    def test_coaching_recent_cardio_reads_feed(self):
        src = _read("coaching.py")
        assert "FROM canonical_cardio_feed" in src
        # _get_performance_delta is intentionally left on raw cardio_log — it is
        # already Postgres-broken (GROUP_CONCAT + non-aggregated GROUP BY), a
        # pre-existing bug flagged separately, not repointed in Slice 4a.
        assert "LEFT JOIN cardio_log cl ON cl.plan_item_id = pi.id" in src


class TestDisplayConsumersReadFeed:
    """Slice 4b — the summary/display surfaces collapse a cross-source ride to
    one row; the literal activity-LOG/CRUD pages deliberately stay raw so a stray
    duplicate stays visible and deletable (decision 2)."""

    def test_connections_files_list_reads_feed(self):
        src = _read("routes/connections.py")
        # the Data-hub Files list + its count both read the deduped feed
        assert "FROM canonical_cardio_feed WHERE user_id = ?" in src
        assert "SELECT COUNT(*) AS n FROM canonical_cardio_feed" in src
        # the old raw-table reads are gone (they showed N copies of one ride)
        assert "FROM cardio_log WHERE user_id = ?" not in src
        assert "SELECT COUNT(*) AS n FROM cardio_log" not in src

    def test_dashboard_cardio_surfaces_read_feed(self):
        src = _read("routes/dashboard.py")
        # recent-cardio strip + unconditioned-cardio nudge. (#957 removed the
        # cardio_total stat — and its `SELECT COUNT(*) FROM canonical_cardio_feed`
        # — from the Today view, so the feed now has two display consumers here,
        # not three. Both remaining surfaces still read the deduped feed.)
        assert src.count("FROM canonical_cardio_feed") >= 2
        # #955: the unconditioned-cardio nudge suppresses once conditions are
        # logged for the event — resolved across the whole cluster (any copy),
        # not just the feed's primary copy id.
        assert "FROM conditions_log cond" in src
        assert "m.cluster_id = cl.cluster_id" in src
        # the raw cardio_log reads for these three surfaces are gone
        assert "SELECT COUNT(*) FROM cardio_log WHERE user_id = ?" not in src
        assert "FROM cardio_log cl\n" not in src
        # the strength count is a different table and stays put
        assert "FROM training_log WHERE user_id = ?" in src

    def test_literal_log_pages_stay_raw(self):
        # decision 2: the literal cardio-LOG list/edit pages keep showing every
        # imported copy, so they must NOT be repointed at the feed.
        for rel in ("routes/cardio.py", "routes/training.py"):
            src = _read(rel)
            assert "canonical_cardio_feed" not in src, rel
