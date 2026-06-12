# V5 Implementation — Track 2 slice 2c.2b: craft-capture integrity (shipped)

**Date:** 2026-06-12
**Branch:** `claude/inspiring-galileo-nvnqys`
**PRs:** [#558](https://github.com/ahorn885/exercise/pull/558) (profile capture) + [#560](https://github.com/ahorn885/exercise/pull/560) (onboarding capture) — both squash-merged to `main` (`a867dc6`, `f0c74c6`)
**Issue:** [#540](https://github.com/ahorn885/exercise/issues/540) (craft axis prereq) · filed [#559](https://github.com/ahorn885/exercise/issues/559) (team-only D-019)

> **Continuing #540?** 2c.2b is **done** (both surfaces). The next slice is **2c.2c — the craft axis** (own-the-bike substitution: `group → group_kind` ladder, road-bike-for-MTB), which now has a real ingestion path. It's a Trigger #3/#5 design slice — scope + sign-off before building. The vocabulary is already settled (see §3) — do **not** re-open it.

---

## 1. What this session was

Started from a question (explain a prior-session note about the #336/#540 "two substitute-strength gates"). That note + the whole #540 create-wiring turned out **already shipped** (PR #556, merged the same day, before this container was cloned) — the #336/#540 overlap was resolved by **partition** (the terrain resolver excludes skill-gated disciplines), not the compose-precedence I initially sketched. With that closed, the live next move per CURRENT_STATE was **slice 2c.2b — craft-capture integrity**, which this session designed (correcting a wrong premise — see §3) and shipped.

## 2. What shipped (PRs #558 + #560)

The discipline-baseline craft columns (`discipline_baseline_cycling.bike_types_available`, `discipline_baseline_paddling.paddle_craft_types`) were **read by Layer 1 and consumed by the X1b.3b craft-substitution narrowing while nothing ever wrote them** — so the craft axis ran on empty data. This adds the write path on both capture surfaces.

- **`athlete_crafts_repo.py`** (NEW) — `load_craft_catalog` / `get_athlete_crafts` / `replace_athlete_crafts` (closed-enum validated, per-family replace-all, **upserts only the craft column** so sibling baselines are preserved) + `evict_layer1_on_crafts_change`. Mirrors `athlete_discipline_weighting_repo`.
- **`athlete.py`** — `BIKE_TYPES = ('road_bike','mountain_bike','gravel_bike','cycling_trainer')` + `CRAFT_LABELS` picker labels (paddle already had `PADDLE_CRAFT_TYPES`).
- **`layer4/context.py`** — `CyclingBaseline.bike_types_available` tightened free-text `list[str]` → `Literal[...]` over the four bike slugs (parity with `paddle_craft_types`), so a stored value can never silently miss the alias lookup (the V4c silent-mismatch class).
- **`templates/onboarding/_crafts_form.html`** (NEW) — shared bike/paddle checkbox partial (anti-drift convention, like `_skills_form`/`_schedule_form`). Field names `bike_types` / `paddle_crafts`; slugs == `craft_discipline_aliases` keys.
- **`routes/profile.py`** — `/profile/crafts` route + `craft_catalog`/`athlete_crafts` in the athlete-tab context (PR #558).
- **`templates/profile/edit.html`** — "Gear you own" form; the checkbox block is the shared include (PR #558 inline → PR #560 partial).
- **`routes/onboarding.py`** — `skills()` passes the catalog; `skills_save()` also persists crafts (replace-all) before advancing, one Layer 1 eviction covering both (PR #560).
- **`templates/onboarding/skills.html`** — includes the partial inside the skills form (PR #560).
- **Tests:** `tests/test_athlete_crafts_repo.py` (repo + closed-enum guard + a recurrence guard: capture enums cover every live `craft_discipline_aliases` key — the craft-domain analogue of V4c's coverage guard); `tests/test_onboarding_skills.py` updated for the extended `skills_save` + new craft cases.

**Scope (Andy-confirmed):** bike + paddle only, on the **existing ratified snake-case slugs**. No vocab adds, **no DDL** (columns existed). SUP deferred (minor); paddle-rafting deferred → **team-only**, filed as #559.

## 3. The premise I had to correct (read before touching craft vocab)

I initially proposed a "reconcile to canonical names" slice on the theory that `craft_discipline_aliases` (snake `mountain_bike`) was inconsistent with `layer0.equipment_items` (sentence-case `Mountain bike`). **Andy flagged that as already-settled, and he was right.** The record:

- **`designs/X1b3b_CraftDisciplineAliases_v1.md`** — craft keying is **snake-case slugs, Andy-ratified**; matched against the athlete's snake craft fields, **not** the equipment catalog. The two vocabularies are deliberately separate consumers. `cycling_trainer → all bike types` is **kept** (Andy). #477 cycling split is **"verified false / superseded"** by the live D-030/D-031/D-032 adds — confirmed: zero `D-006a/b/c` in `etl/output/layer0_etl_v1.6.7.sql`.
- **`research/Vocabulary_Audit_v3.md` §3–4** — bike + paddle are the only craft *vessels*; climb/snow/ski/whitewater kit is the **12 readiness toggles**, not crafts; SUP + Inflatable raft are **kept** as canonical equipment.
- **`research/Craft_Equipment_Vocabulary_Reconciliation_Audit_v3.md`** is **stale** on the cycling split (predates X1b.3b by 2 days) — do not treat its §A/§G D3 as live.

Net: the craft vocabulary is consistent by design (snake slugs end to end on the craft path). 2c.2b was a **capture-wiring** slice, not a reconciliation.

## 4. Verification

- Full suite **2310 passed / 30 skipped**; `etl/tests/` 88 passed. CI green on both PRs (Python suite, Layer 0 gate, JS harness, Vercel; Real-LLM smoke skipped). No DDL.

## 5. Owed / next move

1. **Slice 2c.2c — the craft axis** (NEXT): the `group → group_kind` substitution ladder (own a road bike, race wants MTB → train road; both `group_kind='bike'`), re-running the terrain axis after the craft swap. Builds on the now-real captured crafts. Design lives in the slice-2c.2 handoff §2 (craft axis) + `Modality_Group_Spec_v1` §6. **Trigger #3 (cross-layer, touches the feasibility cascade) + #5 — scope + sign-off first.**
2. **#557 — refresh-path wiring** (terrain): still sequenced behind #208 (refresh route not live). Not urgent.
3. **#559 — team-only D-019** (paddle rafting): gate solo-plan training on a joint plan; deferred until team plans exist.
4. **#539** (tab-closed plan-gen crawl) — still open, go-live tier alongside #540.
5. Pre-existing owed: confirm `layer0.skill_capability_toggles` applied on Neon (#336 gate is data-driven off it).

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` (the #540 section) · 4. **this handoff** · 5. `./scripts/verify-handoff.sh`. **2c.2b is shipped (both surfaces).** Next is **2c.2c** (§5.1) — design slice, do not skip the stop-and-ask. The craft vocabulary is settled (§3) — don't re-open it.

## 6. Stop-and-asks this session
Scope of 2c.2b (tight vs broad; SUP/raft) put to Andy via `AskUserQuestion` across several rounds; he directed tight (existing slugs), defer SUP, file D-019 as team-only. No Trigger #1 (capture forms, no prompt body); no Trigger #2 (no vocab adds); the `Literal` tightening is a Layer 1 model change on a never-populated field (minimal blast radius, flagged).

## 7. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Craft repo (write path) | `athlete_crafts_repo.py` | `def replace_athlete_crafts` (`ON CONFLICT (user_id)`), `def load_craft_catalog`, `class CraftSelectionError` |
| Capture enums | `athlete.py` | `BIKE_TYPES = ('road_bike', 'mountain_bike', 'gravel_bike', 'cycling_trainer')`; `CRAFT_LABELS` |
| Model tightened | `layer4/context.py` | `CyclingBaseline.bike_types_available: list[Literal["road_bike",…]]` |
| Profile route | `routes/profile.py` | `@bp.route('/crafts'`; `def save_crafts`; `craft_catalog=`/`athlete_crafts=` in `edit()` render |
| Onboarding wiring | `routes/onboarding.py` | `skills_save` calls `replace_athlete_crafts`; `skills()` passes `craft_catalog`/`athlete_crafts` |
| Shared partial | `templates/onboarding/_crafts_form.html` | `name="bike_types"`, `name="paddle_crafts"`; included by `profile/edit.html` + `onboarding/skills.html` |
| Tests | `tests/test_athlete_crafts_repo.py`, `tests/test_onboarding_skills.py` | `test_capture_enums_cover_every_craft_alias_key`; `test_post_persists_selected_crafts_in_enum_order` |
| Merged | PRs [#558](https://github.com/ahorn885/exercise/pull/558) + [#560](https://github.com/ahorn885/exercise/pull/560) | squash-merged; full suite 2310 |
