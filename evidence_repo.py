"""Data-access helpers for the science-provenance backbone (#826).

Pure read/write functions against `evidence_sources`, `plan_version_evidence`,
and `evidence_curation_flags`. No HTTP / no Flask blueprint — consumed by the
plan-generation completing pass (deterministic baseline capture), the athlete
"science behind your plan" panel (read), and the admin curation surface.

Two attribution channels, per the issue's locked "mixed" decision:

* Deterministic — `attach_baseline_plan_evidence` links a finished
  `plan_version` to the house-methodology baseline sources (the per-plan-version
  "whys" for v1). Called from the plan-gen completing pass.
* Cited — `record_plan_evidence_citations` is the seam the LLM-cited Layer 3
  path calls once prompts emit source slugs: every cited slug is validated
  against `evidence_sources` (constrained-citation — no free-text research ever
  reaches an athlete); a slug that resolves links the plan, one that doesn't
  writes an `evidence_curation_flags` row for an operator to triage (the
  decision still stands, unattributed) rather than dropping or hard-failing.

Mirrors the repo conventions in `plan_sessions_repo` / `plan_nutrition_repo`:
`?` placeholders (the `_PgConn` shim rewrites to `%s`), dict rows, and the
caller owns the transaction boundary — these helpers do NOT call `db.commit()`.

Schema reference: `init_db.py` `evidence_sources` / `plan_version_evidence` /
`evidence_curation_flags` migrations.
"""

from __future__ import annotations

from typing import Any

# ─── reads: evidence sources ────────────────────────────────────────────────


def list_evidence_sources(
    db: Any, *, status: str | None = None
) -> list[dict[str, Any]]:
    """All evidence sources, newest first, optionally filtered by `status`
    (`active` / `superseded`). Lightweight dicts for the admin catalog."""
    if status is not None:
        cur = db.execute(
            """SELECT id, slug, kind, title, summary, citation, url, status,
                      superseded_by_id, is_baseline, as_of, created_at
                 FROM evidence_sources
                WHERE status = ?
                ORDER BY is_baseline DESC, kind, title""",
            (status,),
        )
    else:
        cur = db.execute(
            """SELECT id, slug, kind, title, summary, citation, url, status,
                      superseded_by_id, is_baseline, as_of, created_at
                 FROM evidence_sources
                ORDER BY is_baseline DESC, kind, title"""
        )
    return [dict(row) for row in cur.fetchall()]


def list_baseline_source_ids(db: Any) -> list[int]:
    """Ids of the active house-methodology baseline sources — the set every
    generated plan is linked to (the deterministic per-plan-version capture)."""
    cur = db.execute(
        "SELECT id FROM evidence_sources "
        "WHERE is_baseline = TRUE AND status = 'active' ORDER BY id"
    )
    return [int(row["id"]) for row in cur.fetchall()]


def resolve_slugs_to_ids(db: Any, slugs: list[str]) -> dict[str, int]:
    """Map active-source slugs → id. Slugs absent from the store (or pointing
    at a superseded row) are simply omitted — the constrained-citation rule:
    only an existing, active source counts as a valid citation."""
    out: dict[str, int] = {}
    for slug in slugs:
        cur = db.execute(
            "SELECT id FROM evidence_sources "
            "WHERE slug = ? AND status = 'active'",
            (slug,),
        )
        row = cur.fetchone()
        if row is not None:
            out[slug] = int(row["id"])
    return out


# ─── reads: the athlete-facing panel ─────────────────────────────────────────


def load_plan_evidence(db: Any, plan_version_id: int) -> list[dict[str, Any]]:
    """Evidence sources linked to `plan_version_id`, ordered for display
    (baseline first, then by kind/title). Feeds the always-visible "science
    behind your plan" panel on the plan view, race-week brief, and race-day
    plan (all three key off the same `plan_version`). Read-only; returns []
    when nothing is linked yet so the panel degrades gracefully."""
    cur = db.execute(
        """SELECT s.id, s.slug, s.kind, s.title, s.summary, s.citation,
                  s.url, s.status, s.is_baseline
             FROM plan_version_evidence pve
             JOIN evidence_sources s ON s.id = pve.evidence_source_id
            WHERE pve.plan_version_id = ?
            ORDER BY s.is_baseline DESC, s.kind, s.title""",
        (plan_version_id,),
    )
    return [dict(row) for row in cur.fetchall()]


# ─── writes: provenance links ────────────────────────────────────────────────


def link_plan_evidence(
    db: Any, plan_version_id: int, source_ids: list[int]
) -> int:
    """Link `plan_version_id` to each evidence source id. Idempotent — the
    composite PK + ON CONFLICT DO NOTHING means a re-run (e.g. a regenerate)
    never accumulates duplicates. Returns the number of links written. Caller
    owns the transaction boundary."""
    written = 0
    for source_id in source_ids:
        cur = db.execute(
            """INSERT INTO plan_version_evidence
                   (plan_version_id, evidence_source_id)
                VALUES (?, ?)
                ON CONFLICT (plan_version_id, evidence_source_id) DO NOTHING""",
            (plan_version_id, source_id),
        )
        # rowcount is best-effort across the shim; count attempts that the
        # conflict-guard didn't reject when the driver exposes it.
        rc = getattr(cur, "rowcount", None)
        written += rc if isinstance(rc, int) and rc > 0 else 0
    return written


def attach_baseline_plan_evidence(db: Any, plan_version_id: int) -> int:
    """Deterministic capture: link a finished plan to the baseline methodology
    sources (the per-`plan_version` "whys" for v1). Returns the number of
    sources considered (links attempted). Caller owns the transaction."""
    baseline_ids = list_baseline_source_ids(db)
    if not baseline_ids:
        return 0
    link_plan_evidence(db, plan_version_id, baseline_ids)
    return len(baseline_ids)


def record_plan_evidence_citations(
    db: Any,
    plan_version_id: int,
    raised_by_layer: str,
    citations: list[dict[str, Any]],
) -> dict[str, int]:
    """Cited-attribution seam (the LLM-cited Layer 3 path). Each citation is a
    dict with `slug` (the cited source) and `context_text` (what the decision
    was). Validates every slug against the active store: a hit links the plan;
    a miss writes/increments an `evidence_curation_flags` row (the decision
    stands, unattributed) — never dropped silently, never hard-failed.

    Returns `{"linked": n, "flagged": m}`. Caller owns the transaction."""
    slugs = [c["slug"] for c in citations if c.get("slug")]
    resolved = resolve_slugs_to_ids(db, slugs)

    linked_ids: set[int] = set()
    flagged = 0
    for citation in citations:
        slug = citation.get("slug")
        context_text = citation.get("context_text") or (slug or "")
        if slug and slug in resolved:
            linked_ids.add(resolved[slug])
        else:
            record_curation_flag(
                db,
                plan_version_id=plan_version_id,
                raised_by_layer=raised_by_layer,
                context_text=context_text,
                cited_token=slug,
            )
            flagged += 1

    if linked_ids:
        link_plan_evidence(db, plan_version_id, sorted(linked_ids))
    return {"linked": len(linked_ids), "flagged": flagged}


# ─── writes: curation gaps ───────────────────────────────────────────────────


def record_curation_flag(
    db: Any,
    *,
    plan_version_id: int | None,
    raised_by_layer: str | None,
    context_text: str,
    cited_token: str | None = None,
) -> None:
    """Record (or increment) a curation gap. When an open flag with the same
    (plan_version_id, cited_token, context_text) already exists we bump its
    `occurrences` rather than inserting a duplicate, so the admin queue stays
    legible. Caller owns the transaction boundary."""
    cur = db.execute(
        """SELECT id FROM evidence_curation_flags
            WHERE status = 'open'
              AND context_text = ?
              AND COALESCE(cited_token, '') = COALESCE(?, '')
              AND COALESCE(plan_version_id, -1) = COALESCE(?, -1)
            LIMIT 1""",
        (context_text, cited_token, plan_version_id),
    )
    existing = cur.fetchone()
    if existing is not None:
        db.execute(
            "UPDATE evidence_curation_flags "
            "SET occurrences = occurrences + 1 WHERE id = ?",
            (existing["id"],),
        )
        return
    db.execute(
        """INSERT INTO evidence_curation_flags
               (plan_version_id, raised_by_layer, context_text, cited_token)
            VALUES (?, ?, ?, ?)""",
        (plan_version_id, raised_by_layer, context_text, cited_token),
    )


def list_curation_flags(
    db: Any, *, status: str = "open", limit: int = 500
) -> list[dict[str, Any]]:
    """Curation flags for the admin triage queue, newest first, filtered by
    `status` (`open` / `resolved` / `dismissed`)."""
    cur = db.execute(
        """SELECT id, plan_version_id, raised_by_layer, context_text,
                  cited_token, occurrences, status,
                  resolved_by_evidence_source_id, created_at, resolved_at
             FROM evidence_curation_flags
            WHERE status = ?
            ORDER BY occurrences DESC, created_at DESC
            LIMIT ?""",
        (status, limit),
    )
    return [dict(row) for row in cur.fetchall()]


def count_open_curation_flags(db: Any) -> int:
    """Count of open curation gaps — drives the admin nav badge."""
    cur = db.execute(
        "SELECT COUNT(*) AS n FROM evidence_curation_flags WHERE status = 'open'"
    )
    row = cur.fetchone()
    return int(row["n"]) if row else 0


def resolve_curation_flag(
    db: Any, flag_id: int, evidence_source_id: int
) -> None:
    """Mark a flag resolved by the source an operator created/picked for it.
    Caller owns the transaction boundary."""
    db.execute(
        """UPDATE evidence_curation_flags
              SET status = 'resolved',
                  resolved_by_evidence_source_id = ?,
                  resolved_at = NOW()
            WHERE id = ?""",
        (evidence_source_id, flag_id),
    )


def dismiss_curation_flag(db: Any, flag_id: int) -> None:
    """Mark a flag dismissed (a gap an operator judged not worth a source).
    Caller owns the transaction boundary."""
    db.execute(
        "UPDATE evidence_curation_flags "
        "SET status = 'dismissed', resolved_at = NOW() WHERE id = ?",
        (flag_id,),
    )


# ─── writes: source authoring ────────────────────────────────────────────────


def create_evidence_source(
    db: Any,
    *,
    slug: str,
    kind: str,
    title: str,
    summary: str | None = None,
    citation: str | None = None,
    url: str | None = None,
    is_baseline: bool = False,
) -> int:
    """Insert an evidence source and return its id. `kind` must be one of
    study / guideline / expert_coach (enforced by the table CHECK). Used by
    the admin "resolve curation gap → create source" action. Caller owns the
    transaction boundary."""
    if kind not in ("study", "guideline", "expert_coach"):
        raise ValueError(
            f"kind={kind!r} not in (study, guideline, expert_coach)"
        )
    cur = db.execute(
        """INSERT INTO evidence_sources
               (slug, kind, title, summary, citation, url, is_baseline)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id""",
        (slug, kind, title, summary, citation, url, is_baseline),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(
            "INSERT INTO evidence_sources RETURNING id returned no row"
        )
    return int(row["id"])
