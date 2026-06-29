# V5 Implementation — #255 onboarding vocab alignment: system_category canonical retag + side-less canonical body parts

**Branch:** `claude/issue-246-h9tv20` · **Epic:** #246 · **Sub-issue:** #255 · **PR:** pending Andy's go (one PR, both halves)

---

## 1. What this session was

Epic #246 (onboarding / Layer-1 data capture) has four open sub-issues; Andy picked **#255** (#254 is in a parallel session). #255 aligns two onboarding vocabularies to the canonical reference data:

- **Enum half** — grow `system_category` from the deployed 8-value enum to the canonical **11** (`research/Vocabulary_Audit_v3.md` §2.2).
- **Body-part half** — replace the Left/Right-doubled injury body-part list with the **side-less canonical** vocab (`layer0.body_parts.canonical_name`) + a dedicated side field.

Both are **Trigger #2 (vocab) + #3 (cross-layer)**. Scoped via AskUserQuestion — Andy chose **full canonical** on each, and **one PR for both halves**.

Investigation corrected two stale premises in the issue text:
- The "8→11" enum move is a **restructure**, not an add (merge endocrine+metabolic, split gi_immune).
- The real cross-layer match surface is **`layer0.supplement_vocabulary.contraindications`** (read by Layer 2E), NOT `layer0.exercises.contraindicated_conditions` (which is empty across all 3105 rows).
- The canonical body-part count is **51** (audit), the deployed table has **54** (incl. Bicep/Biceps + Tricep/Triceps dupes and internal Trachea/Diaphragm flags), not the "41" in the issue/`layer2d` doc.

## 2. Shipped

**Enum half (app):**
- `athlete.py` `KNOWN_SYSTEM_CATEGORIES` → canonical 11.
- `layer4/context.py` `HealthConditionRecord.system_category` Literal → canonical 11.
- `health_inputs_repo.py` `SYSTEM_CATEGORY_LABELS` + `CONDITIONS_BY_CATEGORY` restructured (endocrine_metabolic merge; gi vs immune_autoimmune split; skin/thermoregulation lists added from §2.2; cognitive_mental_health = free-text only).
- `layer2d/builder.py` module doc reconciled (8 → canonical 11; notes the Layer 2E match surface).
- `init_db.py` `_PG_MIGRATIONS`: remap existing `health_conditions_log` rows off the retired slugs (idempotent).

**Enum half (Layer 0):**
- `etl/migrations/layer0/0031_retag_supplement_contraindications_canonical.sql` — in-place UPDATE of `supplement_vocabulary.contraindications` (PK = supplement_id alone → no supersede; standing cache-digest exception → no version bump). `gi_immune`→`gi` (GI-distress, not autoimmune); endocrine/metabolic→endocrine_metabolic. 5 rows: magnesium, carb_powder, iron, electrolyte_mix, sodium_bicarbonate.

**Body-part half (app):**
- `routes/injuries.py` `BODY_PARTS` → `BODY_PART_GROUPS` (canonical 51, side-less, region-grouped); `_save` reads `side` from a dedicated field (`KNOWN_INJURY_SIDES`).
- `athlete.py` `BODY_PART_CONSTRAINTS` rebuilt for all 51 (new parts assigned by anatomical analogy; back labels lowercased).
- `templates/injuries/form.html` — side `<select>` + optgroup body-part select + simplified narrowing JS (no prefix strip; fails open on unmapped values).
- `templates/injuries/list.html` + `templates/profile/_health_tab.html` — show side alongside body_part.
- `routes/profile.py` — injuries query selects `side`.
- `init_db.py` `_PG_MIGRATIONS`: strip Left/Right prefix off existing `injury_log.body_part` + lowercase the back labels (idempotent).

**Body-part half (Layer 0):**
- `etl/migrations/layer0/0032_body_parts_dedupe_singular_add_collarbone.sql` — retire unused singular Bicep/Tricep (live + picker use the plural); add Collarbone. Cache-neutral.

**Tests:** `tests/test_redesign_profile_render.py` (+canonical-11 enum test); `tests/test_injury_form_constraints.py` (CANONICAL_PARTS → 51, no-sided-names test, picker⟺constraint-map consistency test).

## 3. Stop-and-asks this session

- Both halves are Trigger #2/#3 → surfaced findings + options, Andy chose full-canonical on each (AskUserQuestion). Body-part review flags raised: **plural Biceps/Triceps** over the audit's singular (matches live exercise data), **Abdomen dropped** (non-canonical), **skin/thermoregulation condition strings** are new vocab.

## 4. Owed

- **`layer0-apply`** run for `0031` + `0032` (container has no Neon egress; Andy taps the production gate). Both validated locally and idempotent — safe to apply together.
- Public-schema `_PG_MIGRATIONS` (health_conditions_log remap + injury_log prefix strip) auto-apply on deploy.

## 5. Next move

- Epic #246 still open: **#253** (structured supplement capture — new table + Layer 1 builder), **#257** (v3 onboarding form pass, gated/low-pri). #254 in a parallel session.

## 6. §8 anchor table (Rule #10) + §6.3 read order

**§6.3 read order for next session:** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

| File | Anchor string | Check |
|---|---|---|
| `athlete.py` | `'endocrine_metabolic',` and `'immune_autoimmune',` in `KNOWN_SYSTEM_CATEGORIES` | grep |
| `athlete.py` | `'Collarbone':` in `BODY_PART_CONSTRAINTS` | grep |
| `layer4/context.py` | `"cognitive_mental_health",` in `HealthConditionRecord` Literal | grep |
| `health_inputs_repo.py` | `"endocrine_metabolic": [` in `CONDITIONS_BY_CATEGORY` | grep |
| `routes/injuries.py` | `BODY_PART_GROUPS = [` | grep |
| `templates/injuries/form.html` | `name="side"` | grep |
| `init_db.py` | `regexp_replace(body_part, '^(Left|Right) '` | grep |
| `etl/migrations/layer0/0031_retag_supplement_contraindications_canonical.sql` | file exists | ls |
| `etl/migrations/layer0/0032_body_parts_dedupe_singular_add_collarbone.sql` | file exists | ls |

## 7. Mechanically-applicable deferred edits

None — everything landed in-branch. The only deferred action is the `layer0-apply` run (§4), which is a workflow trigger, not a file edit.

## 8. Summary

#255 fully addressed across both halves on `claude/issue-246-h9tv20`. App + two Layer-0 migrations + public-schema remaps + tests; full suite 3752 passed / 30 skipped; local Layer-0 gate PASS with `0031`/`0032` idempotent. One PR pending Andy's go; `layer0-apply` owed on merge.
