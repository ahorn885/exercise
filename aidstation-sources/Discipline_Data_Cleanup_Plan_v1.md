# Layer 0 Discipline-Data Cleanup — Plan & Blast-Radius Analysis (v1)

**Status:** Plan CONFIRMED by Andy 2026-05-30 (§8). Awaiting explicit "go" to implement —
this is a `CLAUDE.md` Trigger #3 (cross-layer / schema) change, so no code is touched until
then. No code or data changed yet.
**Author:** Claude (draft), Andy (review/confirm — all §8 decisions resolved).

---

## 0. Decisions captured (from Andy, 2026-05-30)

1. **Remove disciplines** D-025 Fencing, D-026 Laser Run, D-029 Rifle Shooting. **Keep** D-027 OCR, D-028 XC Skiing.
2. **Complete the fold/rename:** D-003 Hiking + D-015 Orienteering → **Trekking** (one discipline). **Keep** D-001 Trail Running separate/unchanged.
3. **Populate `endurance_profile`** per discipline (Claude suggests values; Andy confirms).
4. **Remove Modern Pentathlon and Biathlon as sports** (`layer0.sports`, not just disciplines).
5. **Remove `discipline_category`** (the column).
6. **Remove `_CATEGORY_ENDURANCE`** (the code dict).
7. **Re-source the nutrition targets** from the chosen disciplines + the new `endurance_profile`, not the prior `discipline_category` prefix-parse.
8. **Observability PR** — still owed, separate workstream (see §9).

---

## 1. The root cause, in one paragraph

Three decisions Andy already made never reached the **single source of truth**
(`etl/layer0/discipline_canon.py`), so the ETL re-asserts the old state on every run: the
pentathlon disciplines are explicitly *kept* in `CANONICAL_NAMES` (not in `REMOVED_IDS`),
and the trekking fold was never written in. Meanwhile the one nutrition heuristic that
needs an endurance signal fragile-parses a **junk free-text column** (`discipline_category`,
copied verbatim from a spreadsheet) instead of a real `endurance_profile`. This plan writes
the decisions into the canon, replaces the junk field with a curated column, and re-sources
nutrition from it. After this, the canon *is* the state — no more drift between "what Andy
said" and "what the ETL does."

---

## 2. New discipline canon (after changes A + B)

**Count: 25 → 21.** (−3 removed in A, −1 merged in B.)

| # | ID | Canonical name | Change |
|---|------|------|------|
| 1 | D-001 | Trail Running | — |
| 2 | D-002 | Road Running | — |
| 3 | D-003 | **Trekking** | renamed from Hiking; absorbs D-015 |
| 4 | D-004 | Swimming | — |
| 5 | D-006 | Road Cycling | — |
| 6 | D-007 | Time-Trial Cycling | — |
| 7 | D-008 | Mountain Biking | — |
| 8 | D-009 | Packrafting | — |
| 9 | D-010 | Kayaking | — |
| 10 | D-011 | Canoeing | — |
| 11 | D-012 | Rock Climbing | — |
| 12 | D-013 | Abseiling | — |
| 13 | D-014 | Via Ferrata | — |
| 14 | D-017 | Snowshoeing | — |
| 15 | D-018 | Mountaineering | — |
| 16 | D-019 | Paddle Rafting | — |
| 17 | D-021 | Uphill Skinning | — |
| 18 | D-022 | Alpine Descent | — |
| 19 | D-024 | Mountain Running | — |
| 20 | D-027 | Obstacle Course Racing | — |
| 21 | D-028 | Cross-Country Skiing | — |
| ~~—~~ | ~~D-015~~ | ~~Orienteering~~ | **merged → D-003** |
| ~~—~~ | ~~D-025~~ | ~~Fencing~~ | **removed** |
| ~~—~~ | ~~D-026~~ | ~~Laser Run~~ | **removed** |
| ~~—~~ | ~~D-029~~ | ~~Rifle Shooting~~ | **removed** |

---

## 3. Change-by-change plan + blast radius

### Change A — Remove D-025, D-026, D-029

**Canon edit** (`etl/layer0/discipline_canon.py`):
- Drop the three from `CANONICAL_NAMES` (lines 52, 53, 56).
- `REMOVED_IDS` → `frozenset({"D-020", "D-023", "D-025", "D-026", "D-029"})` (line 68).
- Update the "25 surviving disciplines" comment (line 28).

**Mechanics already handle it** — `resolve_ids` returns `[]` for removed ids; every
`normalize_*` helper drops dimension/map/gap/substitute/pairing rows that reference them.
No mechanic code change.

**Rows that get dropped at ETL** (all keyed by these ids):
`layer0.disciplines`, `sport_discipline_map`, `phase_load_allocation`,
`discipline_substitutes` (either side), `discipline_pairing` (either side),
`discipline_training_gaps`.

**Stale references to fix:**
- `layer2d/builder.py:86` `_KNOWN_GAP_DISCIPLINES = {"D-022", "D-025"}` — **drop D-025** (defensive/documentary; live set comes from the DTG join, so no runtime break, but it becomes dead + the comment lies). → `{"D-022"}`.
- `etl/layer0/sport_name_aliases.py:107-108` `"Fencing": ["Modern Pentathlon"]` — **remove** (also moot once the sport is removed, §3-C).

**Defensive net:** `etl/layer0/validation/discipline_canon_check.py` already rejects any
non-canonical id left in the id-bearing tables — so a missed reference fails the ETL loudly
rather than silently. Good.

### Change B — Fold D-003 Hiking + D-015 Orienteering → Trekking

**Canon edit:**
- Rename `CANONICAL_NAMES["D-003"]` → `"Trekking"` (line 34).
- Delete `CANONICAL_NAMES["D-015"]` (line 45).
- Add to `ID_REMAP`: `"D-015": "D-003"` (lines 60-63).

After this, `resolve_ids("D-015") → ["D-003"]`, `canonical_name("D-003") → "Trekking"`.
`normalize_*` dedup (first-seen wins) collapses the merged rows; **self-substitute and
self-pairing rows created by the merge are correctly dropped** (`discipline_canon.py:327`,
`:364`).

**⚠ Conditional handling — DECIDED (Andy, 2026-05-30): DROP the conditional.**
- `layer2a/builder.py:63` `_NAV_DISCIPLINE_ID = "D-015"` drives the navigation / sleep-dep
  relevance flag (`builder.py:644`). After the merge, no row is D-015 anymore. **Decision:
  retire the navigation conditional entirely** — Trekking does **not** inherit it.
- Implementation: remove `_NAV_DISCIPLINE_ID` (line 63) and the
  `sleep_dep_relevant = row["discipline_id"] == _NAV_DISCIPLINE_ID` line (644); set the
  flag to a constant `False` (or drop the field's per-discipline source) and update the
  comment at 640-643. **Safe:** the real sleep-dep fueling overlay in Layer 2E is driven by
  event **duration > 20 h** (`layer2e/builder.py` `_SLEEP_DEP_DURATION_THRESHOLD_HR`), an
  independent mechanism — so retiring the discipline-level nav flag does not remove
  sleep-dep handling, only the orienteering-specific trigger. Update `tests/test_layer2a.py`
  cases that assert the flag fires for D-015.

**App/alias fixes:**
- `etl/layer0/sport_name_aliases.py` — collapse `"Hiking"` + `"Orienteering"` (and
  `"Long Distance Orienteering"`) entries into a single `"Trekking"` mapping.
- `discipline_display_names.py` re-exports the canon → "Trekking" propagates automatically.

### Change C — Remove Modern Pentathlon & Biathlon as **sports**

**Architecture clarification (resolves Andy's "are sports even in the DB?" question).**
Sports **are** in the database (`layer0.sports`), and the running app reads sports **only**
from the DB — `SELECT DISTINCT framework_sport FROM layer0.sports`
(`routes/ad_hoc_workouts.py:78`), the version pin (`orchestrator.py:842`), and every
sport-keyed join on `sport_name`. **No runtime code reads the xlsx** — a grep for
`openpyxl`/`Sports_Framework` outside `etl/` returns only the offline ETL and a provenance
comment (`init_db.py:1585`). The xlsx is purely the **ETL source-of-record**: read once,
offline, to build the `layer0.*` tables. This is the intended Layer 0 architecture (same as
disciplines). Eliminating the spreadsheet *as the authoring source* is a real but **separate
future project** (migrate raw framework authoring into curated code/SQL) — out of scope here.

**The real gap:** disciplines have a code-side **canon** (`discipline_canon.py`) that curates
raw rows at ETL time (rename / remove / merge). **Sports have no equivalent.** Today the only
sport-side curation is `sport_name_aliases.py` — and that is **not** a canon: it's a code
dict (not a DB column) that bridges *exercise-DB* sport tags → framework `sport_name` for
Layer 2C matching. It cannot express "remove" or "rename" a framework sport. Separately,
Layer 2E's `sport_profile` is a **derived nutrition label** (`_resolve_sport_profile`, from
`primary_movement`) — **not** a pointer to a canonical sport-name column.

**DECIDED (Andy, 2026-05-30): build the sport canon (code-side).** Add a new
`etl/layer0/sport_canon.py` mirroring `discipline_canon.py`:
- `REMOVED_SPORTS = frozenset({"Modern Pentathlon", "Biathlon"})` (and the structural home
  for future sport renames/merges — `SPORT_NAME_REMAP`, analogous to `ID_REMAP`).
- Applied in `etl/layer0/run.py` after `extract_sports`, cascading the drop across the
  sport-keyed tables: `layer0.sports`, `sport_discipline_map`, `phase_load_allocation`,
  `sport_exercise_map`, `sport_discipline_bridge`, `team_formats`.
- Add a load-time validator (mirror `discipline_canon_check.py`) asserting no removed sport
  survives in any sport-keyed table — so a missed cascade fails the ETL loudly.

This gives sports the same diff-reviewable, drift-proof curation disciplines already have,
and is the clean home for the removal. It does **not** eliminate the xlsx (see above) — it
curates what the ETL pulls from it, exactly as the discipline canon does.

**Consistency:** D-029 Rifle Shooting (removed in A) is exclusive to these two sports, and
D-025 Fencing / D-026 Laser Run are pentathlon-only — so removing the sports and these
disciplines aligns with **no orphans left behind**. D-027 OCR and D-028 XC Skiing are kept
and are used by other sports (OCR standalone; XC Skiing shared with Skimo/Nordic), so they
survive cleanly.

**App-layer hazard (low real risk, must note):** an athlete whose `primary_sport` or
`race_events.framework_sport` equals a removed sport hits `framework_sport_missing`
(`layer4/orchestrator.py:241`) or an empty discipline grid
(`routes/race_events.py:170`). PGE's sports are AR/skimo/ultra — not these two — so no live
athlete is affected, but a one-line guard/seed check before deploy is cheap insurance.

### Change D — Remove `discipline_category` (the junk column)

Clean 6-site vertical slice (the column is read by **only** the endurance heuristic, which
Change E replaces):
1. `etl/layer0/schema.sql:142` — drop column.
2. `etl/layer0/extractors/sports_framework.py:436` — stop extracting xlsx col 3.
3. `etl/layer0/run.py:231` — drop from `disciplines_columns`.
4. `layer2a/builder.py:167` — drop from `_load_disciplines` SELECT; `:649` drop from `Layer2ADiscipline(...)`.
5. `layer4/context.py:227` — drop the `discipline_category` field on `Layer2ADiscipline`.
6. `layer2e/builder.py` — see Change E/F.

`primary_movement` (the sibling column, `schema.sql:143`) is **untouched** — it feeds the
sport-profile vote and stays.

### Change E — Add + populate `endurance_profile` (per discipline)

**Design (recommended):** add nullable `endurance_profile TEXT` to `layer0.disciplines`
(enum: `Pure endurance | Mixed | Technical-dominant`), populated from a **curated map in
`discipline_canon.py`** applied at ETL (same pattern as `CANONICAL_NAMES`) — so the values
are code-reviewed and versioned, not buried in a spreadsheet. Plumb through Layer 2A
(`_load_disciplines` SELECT + `Layer2ADiscipline.endurance_profile`) exactly as
`primary_movement` is plumbed today.

**Values — CONFIRMED (Andy, 2026-05-30): all 21 approved as proposed.** The "Old" column is what the
crude `discipline_category` prefix-parse produced; **★ = my proposal changes today's
behavior** (the point of the exercise — direct curation beats terrain-prefix guessing):

| ID | Discipline | **Proposed** | Rationale | Old (prefix) |
|------|------|------|------|------|
| D-001 | Trail Running | Pure endurance | continuous aerobic | Pure endurance |
| D-002 | Road Running | Pure endurance | continuous aerobic | Pure endurance |
| D-003 | Trekking | Pure endurance | long-duration aerobic load | Pure endurance |
| D-004 | Swimming | **Pure endurance ★** | distance swimming is highly aerobic; the terrain-prefix mislabelled it | Mixed |
| D-006 | Road Cycling | Pure endurance | continuous aerobic | Pure endurance |
| D-007 | Time-Trial Cycling | Pure endurance | sustained threshold | Pure endurance |
| D-008 | Mountain Biking | **Mixed ★** | aerobic base + technical/anaerobic surges (the "unknown category 'Cycling'" warning's discipline) | Pure endurance |
| D-009 | Packrafting | Mixed | aerobic paddling + technical water | Mixed |
| D-010 | Kayaking | Pure endurance | continuous upper-body aerobic (flat/marathon) | Mixed → **★** |
| D-011 | Canoeing | Pure endurance | continuous aerobic paddling | Mixed → **★** |
| D-012 | Rock Climbing | Technical-dominant | strength/skill, low aerobic | Technical-dominant |
| D-013 | Abseiling | Technical-dominant | skill, minimal aerobic | Technical-dominant |
| D-014 | Via Ferrata | Technical-dominant | skill/strength | Technical-dominant |
| D-017 | Snowshoeing | Pure endurance | sustained aerobic locomotion | Pure endurance |
| D-018 | Mountaineering | **Mixed ★** | long aerobic approach + technical sections | Technical-dominant |
| D-019 | Paddle Rafting | Mixed | aerobic + technical whitewater | Mixed |
| D-021 | Uphill Skinning | Pure endurance | sustained aerobic climb | Pure endurance |
| D-022 | Alpine Descent | **Technical-dominant ★** | downhill skill, minimal aerobic load | Pure endurance |
| D-024 | Mountain Running | Pure endurance | aerobic + vert | Pure endurance |
| D-027 | Obstacle Course Racing | Mixed | aerobic + strength obstacles | Mixed (defaulted) |
| D-028 | Cross-Country Skiing | Pure endurance | quintessential aerobic | Pure endurance |

The notable corrections (★) are Swimming, MTB, Kayaking/Canoeing, Mountaineering, Alpine
Descent — precisely the disciplines the terrain-prefix got wrong. All confirmed by Andy.

### Change F — Remove `_CATEGORY_ENDURANCE`; re-source nutrition targets

The daily-CHO math is **sound** and stays: `_cho_band_position` share-weights endurance
labels into a 0–1 band position → `_compute_macros_for_phase` maps it to CHO g/kg
(`layer2e/builder.py:464-533`). The only change is the **source of the label**:
- `_endurance_profile(d)` (`builder.py:207`) → read `d.endurance_profile` directly; drop
  the prefix-parse and delete `_CATEGORY_ENDURANCE` (`builder.py:174-181`).
- Default/unknown handling stays (None → "Mixed", logged).

Everything downstream of the label is unchanged. The race-day path
(`_resolve_sport_profile` → `_SPORT_PROFILE_CHO_MOD`, sourced from `primary_movement`) is
**fully independent** and untouched. The `Layer2EPayload` shape is unchanged, so its **9
consumers** (orchestrator, plan_create, per_phase prompt, race_week_brief, validator, cache
wrappers, both refresh tiers) need no changes — only the *numbers* shift, intentionally.

### 3.5 Per-discipline column architecture — no redundancy after cleanup (Andy Q, 2026-05-30)

**Concern:** "doesn't this imply several extra columns again? why not resolve all nutrition
from discipline + endurance_profile alone? why ALSO a sport_profile?"

**Answer: not redundant — two orthogonal axes, both load-bearing.** After this cleanup a
discipline carries exactly two classification columns (down from three; the junk one goes):

| Column | Axis | Feeds | Verdict |
|------|------|------|------|
| ~~`discipline_category`~~ | terrain (free text) | nothing but the endurance prefix-parse | **REMOVE (junk)** |
| `endurance_profile` (new) | aerobic dependency | **daily** macro CHO band (`_cho_band_position`) | keep — *how carb-dependent is the load* |
| `primary_movement` | movement modality | **race-day** CHO-rate modifier (`_resolve_sport_profile` → `_SPORT_PROFILE_CHO_MOD`) + protein/strength flag (climbing) | keep — *how much fuel absorbable while doing it* |

`endurance_profile` and `sport_profile` answer **different physiological questions**: a
pure-endurance **swim** and a pure-endurance **bike** share an `endurance_profile` but have
opposite race-day fueling ceilings (swim ×0.6 vs bike ×1.0). `endurance_profile` cannot
express absorption-rate; the movement axis can — and it's the only axis that splits swim
from paddle (both "Water / *"), which is why it was added (PR #156 handoff). So we are
netting **down** to two real axes, not re-accumulating.

**`primary_movement` consumers (verified grep, 2026-05-30):** only Layer 2E —
`_movement_sport_profile` (`builder.py:223`) and the protein band (`builder.py:486`). It is
**NOT** used for exercise substitution. The substitution/strength engine uses a *different*
column, per-exercise `movement_pattern` (`coaching.py:343`, `rx_engine.py`, `current_rx`) —
a separate concept on the exercise tables, unaffected by this cleanup. (Easy to conflate;
they live in different layers.) **`primary_movement` stays.**

**Option noted, not taken:** the `movement → profile → modifier` indirection could be
collapsed into a per-discipline race-day-fuel factor, but that's a behavior-changing
redesign, not a cleanup. Out of scope; `_resolve_sport_profile` stays as-is.

---

## 4. Blast-radius summary

### Orphaned / now-dead (remove)
- `_CATEGORY_ENDURANCE` dict; `discipline_category` column + its 6-site plumb.
- D-025 in `_KNOWN_GAP_DISCIPLINES` (`layer2d/builder.py:86`).
- `sport_name_aliases` entries: Fencing; Hiking/Orienteering/Long-Distance-Orienteering (→ Trekking); pentathlon/biathlon alias targets.
- All `layer0.*` rows keyed to D-025/026/029 and the two removed sports (dropped at ETL).

### Broken if not fixed
- **Navigation conditional** (`_NAV_DISCIPLINE_ID = "D-015"`) — dies on the fold. **Decided: retire it** (drop, don't repoint — Trekking carries no nav conditional). Remove the constant + flag source; sleep-dep overlay stays (duration-driven in 2E). **(functional)**
- **Tests** asserting `len(CANONICAL_NAMES) == 25`, D-025/D-029 names, D-015 presence, "Orienteering/Navigation" label, D-003="Hiking", D-025 in training_gaps (inventory in §7). **Mandatory** — these encode the *old* canon; when the canon changes they must change with it or the suite goes red and CI blocks the PR. Updating them is part of the change, not optional cleanup.
- **Athletes** with `primary_sport`/`framework_sport` = a removed sport (none live; guard anyway).

### Disrupted (intended behavior change — needs eyes, not fixes)
- Daily CHO/macro targets shift for any plan including Swimming, MTB, Kayaking, Canoeing, Mountaineering, or Alpine Descent (the ★ corrections). This is the desired outcome of re-sourcing; worth a before/after spot-check on a PGE plan.

### Confirmed NOT affected
- `primary_movement` and the entire race-day sport-profile path.
- `Layer2EPayload` shape + its 9 consumers (output numbers change, contract doesn't).
- The validator (`discipline_canon_check.py`) — defensive, catches stragglers.

---

## 5. Sequenced execution plan

1. **Canon** (`discipline_canon.py`): A (removals) + B (rename/remap) + E (curated `endurance_profile` map). One reviewable diff = the whole policy.
2. **Sport-canon** (new `etl/layer0/sport_canon.py`): `REMOVED_SPORTS` + cascade-apply in `run.py` + load-time validator.
3. **Schema + ETL**: drop `discipline_category` (D); add `endurance_profile` (E) to `schema.sql`, extractor, `run.py` columns.
4. **Migration (Neon)**: `ALTER TABLE layer0.disciplines DROP COLUMN discipline_category, ADD COLUMN endurance_profile TEXT;` + re-run ETL to repopulate (the canon/curated map fills it). Mirror the `primary_movement` migration convention in `etl/sources/`.
5. **Layer 2A**: SELECT swap (`discipline_category` out, `endurance_profile` in) + `Layer2ADiscipline` field swap (`layer4/context.py`) + **retire** `_NAV_DISCIPLINE_ID` / the nav conditional.
6. **Layer 2E** (F): `_endurance_profile` reads the column; delete `_CATEGORY_ENDURANCE`.
7. **Layer 2D**: drop D-025 from `_KNOWN_GAP_DISCIPLINES`.
8. **Tests**: update the §7 inventory; add a guard test that every canonical discipline has a non-null `endurance_profile`.
9. **Spec docs**: amend `Layer2E_Spec.md` §5.3.3 and the Layer 0 ETL spec (current version) to describe `endurance_profile` sourcing; leave historical `_vN` specs untouched.
10. **Deploy (Andy's hands)**: run the migration + ETL on Neon, redeploy, spot-check a fresh PGE plan (expect the §4 "disrupted" CHO shifts; expect the prior `unknown discipline_category 'Navigation'/'Cycling'` warnings to be **gone**).

This also retires CARRY_FORWARD item **(D)** data-hygiene (`unknown discipline_category`)
and likely improves item **(B)** (D-015 "Navigation" spurious banding) since the discipline
is now Trekking with a curated endurance profile.

---

## 6. Migration / deploy ownership

All schema + ETL changes are code-side and test-covered here. The **Neon migration + ETL
re-run + redeploy is Andy's hands** (same as the standing owed-deploys). The migration is
additive-then-subtractive on a dimension table; the canon repopulates `endurance_profile`
on re-run, so order is: deploy code → run migration → run ETL → verify.

---

## 7. Test impact inventory (update these)

| Test | What | Fix |
|------|------|------|
| `etl/tests/test_discipline_canon.py:36` | `len(CANONICAL_NAMES) == 25` | → 21 |
| `etl/tests/test_discipline_canon.py:45` | merged-id check | add D-015→D-003 |
| `etl/tests/test_discipline_canon.py:52-53` | D-025/D-029 names | remove / assert None |
| `etl/tests/test_v11_parsers.py:1180-1191` | `"D-025" in by_id` (training_gaps) | drop D-025 |
| `tests/test_discipline_display_names.py:22` | count `== 25` | → 21 |
| `tests/test_layer2a.py:219, 301, 557…` | D-015 / "Orienteering / Navigation" | → D-003 / "Trekking" |
| `tests/test_layer2c.py:586, 602-628` | D-003 = "Hiking" | → "Trekking" |
| `tests/test_layer2e.py:113-167` | D-003/D-015 mappings; `discipline_category` fixtures | rework onto `endurance_profile` |
| `tests/test_race_events_repo.py`, `test_layer4_orchestrator.py` | D-015 refs | → D-003 |
| **new** | every canonical discipline has non-null `endurance_profile` | add guard |

**No ID renumbering.** Names and counts are updated; the discipline ID space stays
stable-with-gaps (D-005/016/020/023 already removed). Tests reference IDs directly, so the
fix is name/count edits — not a renumber sweep. (Renumbering is the R6 change that silently
broke the old Layer 2E dicts; we don't repeat it.)

---

## 8. Decisions — RESOLVED (Andy, 2026-05-30)

1. **`endurance_profile` values** — ✅ all 21 approved as proposed (§3-E).
2. **Navigation conditional** — ✅ **DROP** it. Trekking does not inherit the nav/sleep-dep flag; retire `_NAV_DISCIPLINE_ID`.
3. **Sport removal mechanism** — ✅ **code-side** — build `etl/layer0/sport_canon.py` with `REMOVED_SPORTS` (§3-C). Gives sports the curation disciplines already have; the xlsx stays the offline source, not a runtime dependency.
4. **Branch** — ✅ new branch `claude/discipline-canon-cleanup` (distinct from #314 Neon fix / #315 plan-gen quality).
5. **ID renumbering** — ✅ **NO renumber.** Update *names* (D-003 → Trekking) and *counts* (25 → 21) only. IDs stay stable-with-gaps (D-005/016/020/023 already gone); renumbering is the R6 pain that silently broke the old 2E dicts — avoid it.

**Remaining gate:** Andy's explicit **"go"** to start implementation. This is a Trigger #3
(cross-layer / schema) change per `CLAUDE.md` — no code is touched until then. Open
sub-question to confirm at go-time: whether to file the GitHub issue(s) for this workstream
(backlog SoT per `CLAUDE.md`) before or alongside the implementation PR.

---

## 9. Observability PR (separate, still owed)

Independent of this cleanup. Both PR #314 and #315 explicitly defer it:
> "Observability (block-content logging + partial-plan view + incremental persist) —
> approved separately, lands in its own PR."

It does **not** exist yet. Tracked here so it isn't lost; it should be its own branch/PR and
does not gate (nor is gated by) the discipline cleanup.

---

## 10. Retiring the xlsx as source-of-record (tracked concern — Andy, 2026-05-30)

**Andy's worry:** "a future ETL will fuck us up by drawing from that stale xlsx." Valid —
`Sports_Framework_v11.xlsx` still physically contains Fencing, Modern Pentathlon, Biathlon,
Hiking, Orienteering rows. They don't reach the DB only because the ETL transforms them.

**Why this cleanup is *safe* against re-drift (the canon is the guardrail):**
- The discipline canon (and the new `sport_canon.py`) is applied on **every** ETL run, so a
  re-run re-removes / re-renames / re-merges the stale rows deterministically. This is the
  whole reason we chose code-side canon over editing the xlsx — the curation is durable and
  diff-reviewable, not a one-time spreadsheet edit that the next export could undo.
- The load-time validators (`discipline_canon_check.py` + the new sport validator) **fail
  the ETL loudly** if any removed id/sport survives into an id/sport-keyed table. A stale
  xlsx row that slips the canon is caught, not silently shipped.

**Residual risk (what the canon does NOT protect):** the xlsx remains authoritative for
everything the canon doesn't override — durations, phase-load values, injury text, evidence
notes, sport flags. Re-authoring the xlsx, or adding a discipline/sport there without a
corresponding canon decision, reintroduces drift. The binary format also means changes
aren't diff-reviewable.

**The real fix (separate future project — FILE AS GITHUB ISSUE):** retire the xlsx as the
Layer 0 source-of-record. Migrate the authoritative framework data into version-controlled,
diff-reviewable code/SQL seeds (the canon modules are already the curation half; this is the
*data* half). Until then:
- **Near-term doc guard (cheap, do with this cleanup):** add a header banner to
  `Sports_Framework_v11.xlsx`'s provenance note / the ETL `run.py` and `etl/sources/README`
  stating the xlsx is a **frozen source** — disciplines/sports are curated in
  `discipline_canon.py` / `sport_canon.py`, and any add/remove/rename MUST go through the
  canon, never the spreadsheet alone.
- **Issue to file:** "Retire Sports_Framework xlsx as Layer 0 source-of-record → curated
  code/SQL seeds" (v2 track, `area:etl`). Names the long-term elimination Andy wants so a
  future ETL can't draw from a stale blob.
