-- 0038_disciplines_requires_team.sql
--
-- #559 (WS-3 T-3.3) — add `requires_team boolean NOT NULL DEFAULT false` to
-- `layer0.disciplines`, so Layer 2A can gate team-only disciplines out of a
-- solo athlete's discipline set (`_resolve_inclusion`, layer2a/builder.py) —
-- driven entirely by this column, never a hardcoded discipline list.
--
-- "Solo" is derived from existing data (no new athlete-facing question): an
-- athlete counts as on a team if they have at least one
-- `athlete_network_links` row whose `relationship_types` contains
-- `"race_teammate"`; no such link means solo
-- (`Layer1Payload.is_solo_athlete`).
--
-- Which disciplines are `requires_team = true`? Investigated
-- `layer0.sports.team_vs_solo` and `layer0.team_formats` for any discipline
-- backed ONLY by a team-mandatory sport with no solo variant. Two sports are
-- unambiguously team-mandatory with no individual option: Adventure Racing
-- ("Teams of 4 ... all members must finish sections together") and Swimrun
-- ("Teams of 2 (mandatory) ... Solo format emerging"). But `requires_team`
-- lives on `layer0.disciplines` — the generic physical-activity canon (Trail
-- Running, Swimming, Rock Climbing, Kayaking, ...) — not on `layer0.sports`,
-- and every discipline `layer0.phase_load_allocation` links to Adventure
-- Racing or Swimrun is ALSO practiced solo elsewhere in the canon (e.g.
-- Swimming under Aquathlon/Triathlon/Open Water Marathon Swimming, all
-- "Individual"; Kayaking under Canoe/Kayak Marathon "Individual (K1)";
-- Road Running under Marathon/Ultramarathon, all "Individual"). The handful
-- of AR-only disciplines in the PLA join (Rock Climbing, Abseiling, Via
-- Ferrata, Snowshoeing, Mountaineering, Paddle Rafting) are solo-practicable
-- activities (climbing gyms, solo mountaineering, solo snowshoeing) that
-- simply aren't yet curated as standalone sports elsewhere — a curation gap,
-- not team-only evidence (compare Skimo, which uses the same "climbing"
-- constituent movement and explicitly offers an "Individual (solo)" format).
--
-- No discipline in the existing data is unambiguously team-only. Per the
-- task's own rule (do not invent classifications or hardcode a guess), this
-- migration adds the column with every row left at the DEFAULT false and
-- flags the "which disciplines (if any) are actually team-only" question as
-- a follow-up decision for Andy — see the T-3.3 handoff report.
--
-- Cache-neutral structural edit (README §"Two edit shapes", shape 1): no row
-- changes served output (every row's `requires_team` is `false`, matching
-- the pre-migration absence of any team gating), so no `etl_version` bump —
-- serving picks up the new column immediately with caches staying warm.
--
-- Idempotent: `ADD COLUMN IF NOT EXISTS`.

BEGIN;

ALTER TABLE layer0.disciplines
  ADD COLUMN IF NOT EXISTS requires_team boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN layer0.disciplines.requires_team IS
  'True when this discipline can only be trained/raced as part of a mandatory team (no solo variant exists). Drives Layer 2A''s _resolve_inclusion hard gate excluding the discipline for a solo athlete (Layer1Payload.is_solo_athlete), ahead of race/athlete/curator precedence. All rows default false as of #559/T-3.3 — no discipline in the existing sports/team_formats data was found to be unambiguously team-only; Andy to confirm which (if any) discipline_id values should flip to true.';

COMMIT;

-- End of 0038_disciplines_requires_team.sql
