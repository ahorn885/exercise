"""Guards on the #826 science-provenance schema + seed in `init_db`.

The evidence tables reference `plan_versions`, which is created in the
`_PG_MIGRATIONS` list (not `PG_SCHEMA`). FK targets must be created before the
referencing table, so these tests pin the ordering — a future reshuffle that
moves `evidence_sources` before `plan_versions`, or `plan_version_evidence`
before `evidence_sources`, would silently break `init_postgres` on a fresh DB.
"""

import init_db

_MIGRATIONS = [m for m in init_db._PG_MIGRATIONS if isinstance(m, str)]


def _first_index(substr: str) -> int:
    for i, stmt in enumerate(_MIGRATIONS):
        if substr in stmt:
            return i
    return -1


def test_evidence_tables_present_in_migrations():
    for table in (
        "CREATE TABLE IF NOT EXISTS evidence_sources",
        "CREATE TABLE IF NOT EXISTS plan_version_evidence",
        "CREATE TABLE IF NOT EXISTS evidence_curation_flags",
    ):
        assert _first_index(table) >= 0, f"missing migration: {table}"


def test_fk_targets_created_before_referencing_tables():
    """plan_versions → evidence_sources → (plan_version_evidence,
    curation_flags, training_methods ALTER). Ordering = FK safety on init."""
    pv = _first_index("CREATE TABLE IF NOT EXISTS plan_versions")
    sources = _first_index("CREATE TABLE IF NOT EXISTS evidence_sources")
    links = _first_index("CREATE TABLE IF NOT EXISTS plan_version_evidence")
    flags = _first_index("CREATE TABLE IF NOT EXISTS evidence_curation_flags")
    tm_alter = _first_index("ALTER TABLE training_methods ADD COLUMN IF NOT EXISTS evidence_source_id")

    assert pv >= 0 and sources > pv, "evidence_sources must follow plan_versions"
    assert links > sources, "plan_version_evidence must follow evidence_sources"
    assert flags > sources, "evidence_curation_flags must follow evidence_sources"
    assert tm_alter > sources, "training_methods FK must follow evidence_sources"


def test_evidence_sources_kind_constraint_is_three_kinds():
    """The only credible kinds are study | guideline | expert_coach — no
    generic internal/heuristic kind (a gap is a curation flag, not a 4th kind)."""
    stmt = _MIGRATIONS[_first_index("CREATE TABLE IF NOT EXISTS evidence_sources")]
    assert "kind IN ('study', 'guideline', 'expert_coach')" in stmt


def test_baseline_seeds_well_formed():
    import evidence_catalog
    seeds = evidence_catalog.seed_rows()
    assert len(seeds) >= 10  # 5 baseline + the non-baseline catalog
    slugs = set()
    allowed = {"study", "guideline", "expert_coach"}
    baseline_count = 0
    for slug, kind, title, summary, citation, url, is_baseline in seeds:
        assert slug and slug not in slugs, f"duplicate/empty slug: {slug!r}"
        slugs.add(slug)
        assert kind in allowed, f"bad kind for {slug}: {kind}"
        assert title, f"empty title for {slug}"
        assert citation, f"source {slug} should carry a citation"
        if is_baseline:
            baseline_count += 1
    assert baseline_count >= 3, "expected a baseline methodology set"
    # init_db re-exports the catalog rows for seeding.
    assert init_db.EVIDENCE_SOURCE_SEEDS == seeds


def test_citable_catalog_matches_seeded_slugs():
    """The prompt allowlist must be exactly the seeded slugs — the
    constrained-citation guarantee that the model is only told about sources
    that exist in the store."""
    import evidence_catalog
    catalog_slugs = {c["slug"] for c in evidence_catalog.citable_catalog()}
    seed_slugs = {r[0] for r in evidence_catalog.seed_rows()}
    assert catalog_slugs == seed_slugs == evidence_catalog.all_slugs()
