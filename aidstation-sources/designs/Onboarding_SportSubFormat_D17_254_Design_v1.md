# Onboarding Sport Sub-Format Capture — D-17 / #254 Design

**Version:** 1.0
**Date:** 2026-06-29
**Status:** **Ratified by Andy 2026-06-29** — approach "Default sub-format + override" (AskUserQuestion); all §2 decisions, the five §2.1 defaults, the D1 storage model, the §3 default-propagation trade-off, and guard-first sequencing **approved**. Implementation in progress.
**Issue:** [#254](https://github.com/ahorn885/exercise/issues/254) — "Onboarding: map a race goal to the correct sport sub-format." Parent epic #246 (onboarding & athlete data capture, Layer 1).
**Backlog row:** D-17 (Sheet 3 / Sheet 5 naming mismatch).
**Affects:**
- `layer0.sport_discipline_bridge` / a new `layer0.sport_sub_format_map` reference table (the onboarding option source).
- `routes/race_events.py` (`_framework_sport_choices`, `_resolve_effective_framework_sport`, the race-event form handler) + the onboarding/profile race-event template.
- `race_events.framework_sport` storage semantics (Layer 1 → Layer 2A contract).
- `layer2a/builder.py` — a loud-failure guard; the existing `_strip_sub_format` workaround is retained, not replaced.
- Spec amendments: `Athlete_Onboarding_Data_Spec_v6.md` §H.2, `Layer2A_Spec.md` §5.1 / §6 (D-17) / §12 (2A-3).

**Cross-references:**
- `Layer2A_Spec.md` §5.1 (sport naming caveat / D-17 strip-and-re-lookup), §6 (D-17 drift row), §12 (open item 2A-3).
- `Race_Events_D66_Design_v1.md` — establishes the `race_events` table + the §H.2 onboarding target-event step this design extends. The `race_format` enum it added (`single_day` / `expedition_ar` / …) is a **periodization** format and is orthogonal to the **sport sub-format** this design captures — do not conflate them.
- `Athlete_Onboarding_Data_Spec_v6.md` §H.2 (target-event capture; "Target Sport / Format").
- Issue #885 / #892 — `_framework_sport_choices` was made a structured select sourced from `sport_discipline_bridge` to stop free-text values from resolving to an empty discipline grid. This design must preserve that "every selectable option resolves to a non-empty set by construction" invariant.

---

## 1. Purpose

Resolve the **Sheet 3 / Sheet 5 naming mismatch (D-17)** on the *capture* side so that a race goal entered during onboarding maps to the correct sport **sub-format**, and Layer 2A's phase-load joins resolve to real rows.

### 1.1 The mismatch, confirmed in live Layer 0 data (`etl/output/layer0_etl_v1.9.0.sql`)

Five sports use a **top-level** name in Sheet 3 (`sport_discipline_map`, and the `sport_discipline_bridge` that backs onboarding) but **sub-format** names in Sheet 5 (`phase_load_allocation` + `phase_load_weekly_totals`):

| Top-level (Sheet 3 / bridge — what onboarding offers) | Sub-formats (Sheet 5 — what Layer 2A joins) |
|---|---|
| `Triathlon` | `Triathlon (Sprint)` / `(Standard / Olympic)` / `(Half / 70.3)` / `(Full / Ironman 140.6)` |
| `Skimo` | `Skimo (Sprint)` / `(Vertical / VK)` / `(Individual / Team)` / `(Long Distance / Grand Traverse)` |
| `Long Distance / Endurance Cycling` | `(Road / Gran Fondo)` / `(Gravel)` / `(Enduro)` / `(Time Trial)` / `(XC Mountain Biking)` |
| `Canoe / Kayak Marathon` | `(ICF Competition)` / `(Ultra-Distance)` |
| `Open Water Marathon Swimming` | `(10km / Olympic Distance)` / `(25km / Ultra Distance)` |

All other sports (Adventure Racing, the marathons, Aquabike, Duathlon, …) use the **same name** in both sheets and are unaffected. AR is identical in both tables — which is why this has sat in the icebox while Andy dogfoods an AR plan.

### 1.2 The live consequence

The onboarding "Race event type" select (`routes/race_events.py:_framework_sport_choices`) is sourced from `sport_discipline_bridge`, which only carries top-level names. An athlete targeting a triathlon can therefore only pick `"Triathlon"`. That string is stored as `race_events.framework_sport` and passed to Layer 2A as `framework_sport`. In `layer2a/builder.py`:

- `_strip_sub_format("Triathlon")` → `"Triathlon"` (no parenthetical to strip) → the SDM lookup **resolves** (the bridge/SDM key is top-level), so disciplines are returned.
- The PLA `LEFT JOIN` keys on `pla.sport_name = framework_sport = "Triathlon"`. PLA has **no `"Triathlon"` row** — only the four sub-format rows. Every discipline's phase-load bands come back **NULL**. `phase_load_weekly_totals` (also sub-format-keyed) misses identically.

Result: for all five sports, Layer 2A silently produces disciplines with **no phase-load allocation** → the volume engine has nothing to renormalize into weekly hours → a degraded/empty plan, with no loud signal. The `_strip_sub_format` workaround only helps the *reverse* direction (a sub-format name → strip for SDM); it is inert here because onboarding never produces a sub-format name in the first place.

### 1.3 What "fixed" means

1. Onboarding stores a `framework_sport` that is a **real PLA `sport_name`** (a sub-format name for the five sports; unchanged for everyone else).
2. The athlete who does nothing special still gets a sensible **default** sub-format (no dead-end, no NULL bands).
3. The athlete who knows their race can **override** to the correct sub-format.
4. Layer 2A **fails loudly** (flag + log) rather than silently if a sub-format parent ever reaches it unresolved — protecting against legacy rows and capture-path regressions.

---

## 2. Decisions

> **Decision revision (2026-06-29, ratified by Andy) — storage model reversed from D1 (resolved-name) to the two-column model.** Implementation of slice B surfaced that `framework_sport` is consumed *as the top-level key* by the discipline-bridge + terrain machinery (`routes/race_events.py:_disciplines_for_framework_sport` and the `_race_terrain_editor.html` discipline endpoint both look it up in `sport_discipline_bridge`, which is top-level-keyed). Storing the resolved sub-format name there would return `[]` from the bridge → collapse the discipline grid + per-row terrain selects → **re-introduce the #892 data-loss bug**, and would force strip logic into *every* top-level consumer. The two-column model (originally open-Q2, rejected) is therefore now the ratified choice: it leaves all top-level consumers untouched and localizes the change to one composition point. Andy also confirmed (chat) the defaults live in **Layer 0** (D2). The original D1 row is struck through below; D2/D4 stand; D3/D5/D6 are restated for the two-column model.

| # | Decision | Rationale |
|---|---|---|
| ~~D1~~ | ~~`race_events.framework_sport` stores the fully-resolved sub-format name.~~ **SUPERSEDED → D1′.** | Reversed — see the revision banner above (top-level consumers break). |
| **D1′** | **Two-column storage.** `race_events.framework_sport` stays the **top-level** name (unchanged; all bridge/terrain consumers untouched). A **new `race_events.sport_sub_format` column** holds the athlete's chosen full PLA sub-format name (NULL = use the parent's curated default). The Layer-4 orchestrator **composes** the Layer 2A input: `framework_sport_for_2a = sport_sub_format or <parent default> or framework_sport`. | Smallest blast radius — one composition point vs. N strip sites; the entire existing top-level machinery is left alone; round-trips trivially on edit (two columns ↔ two selects, no name-parsing). `race_events` is *public* schema, so the column add + backfill auto-apply on deploy. |
| D2 | **The default sub-format is a Layer 0, data-driven fact** (`layer0.sport_sub_format_map`): one row per `(parent_sport, sub_format_sport)`, `is_default` marks exactly one per parent, `display_label` = the athlete-facing short label. Onboarding reads options + default from it; no curation in app code. **Ratified ("layer 0").** | DB-is-source-of-truth (CLAUDE.md). Curator owns the default + option list. **Shipped slice A** (migration 0031 + `validate_layer0` check). |
| D3 | **Onboarding/profile renders a second "sub-format" select**, shown only when the chosen parent has rows in `sport_sub_format_map`. Options = that parent's rows; the `is_default` row is pre-selected. Submit sets `race_events.sport_sub_format`. Parents with no sub-formats keep today's single-select behaviour. | "Default + override": default pre-filled, athlete may change it. The parent `framework_sport` select is unchanged, so the #885 non-empty-by-construction invariant holds. |
| D4 | **Layer 2A loud-failure guard.** When `framework_sport` is exactly a `_SUB_FORMAT_SPORTS` parent **and** disciplines load but zero PLA rows joined, emit an `error` `UnresolvedFlag` + `hitl_required = True` + a Rule-#15 `print`. | Turns the silent NULL-bands data-loss into a loud failure for legacy/regression inputs. **Shipped slice 2.** |
| D5 | **One-time backfill** sets `race_events.sport_sub_format` = the parent's default for existing rows whose `framework_sport` is one of the five parents and whose `sport_sub_format` is NULL. *Public*-schema `_PG_MIGRATIONS` → auto-applies on deploy. | Andy's own row is AR (unaffected), so risk is ~nil, but the backfill makes the cutover deterministic. |
| D6 | **Sub-format change reuses the existing `framework_sport`-change invalidation path** (`evict_on_target_event_framework_sport_change`); the route fires it when `sport_sub_format` changes too. No new invalidation rule. | A sub-format change shifts the composed Layer 2A input, the same cache axis a `framework_sport` change already evicts. |

### 2.1 Defaults (D2 `is_default`) — **ratified 2026-06-29; seeded in migration 0031**

| Parent sport | Proposed default sub-format | Why |
|---|---|---|
| `Triathlon` | `Triathlon (Standard / Olympic)` | The canonical reference distance; the modal age-group race. |
| `Skimo` | `Skimo (Individual / Team)` | The standard mass-start format; Sprint/Vertical are specialist. |
| `Long Distance / Endurance Cycling` | `Long Distance / Endurance Cycling (Road / Gran Fondo)` | Highest mass participation of the five LDC formats. |
| `Canoe / Kayak Marathon` | `Canoe / Kayak Marathon (ICF Competition)` | The standardized marathon format vs. the bespoke ultra. |
| `Open Water Marathon Swimming` | `Open Water Marathon Swimming (10km / Olympic Distance)` | The standard marathon-swim distance. |

Ratified by Andy 2026-06-29 ("approve your original suggestions"); seeded as the `is_default` rows in migration `0031_sport_sub_format_map.sql`.

### 2.2 Sub-decisions deferred to the implementation PR

- Exact column types / constraints on `sport_sub_format_map` (mirror the existing Layer 0 table idiom: `etl_version` / `etl_run_at` / `superseded_at`, partial-unique on `(parent_sport, sub_format_sport)` where `superseded_at IS NULL`; a `validate_layer0` check that exactly one `is_default` exists per parent).
- Whether the second select is a dependent control populated client-side from a JSON blob vs. a server round-trip on parent change. (Lean: ship the JSON-blob client-side populate — the option set is tiny and static per parent.)
- Round-trip decomposition on profile edit: stored `"Triathlon (Standard / Olympic)"` → repopulate parent select = `"Triathlon"` + sub-format select = `"(Standard / Olympic)"`, via the same whitelist parse `_strip_sub_format` uses. Helper placement (`routes/race_events.py`).
- Copy for the sub-format select label + helper text (athlete-facing; coaching voice).

---

## 3. Why not the alternatives

| Approach | Why not (for v1) |
|---|---|
| **Explicit picker only, no default** | A required second step for five sports; an athlete who skips/defers it dead-ends to NULL bands. Andy chose default+override specifically so the no-action path still resolves. |
| **Infer sub-format from race distance/duration** | Needs a distance→sub-format mapping table that does not exist, plus a fallback for ambiguous/missing distances. Fragile; Sprint vs. Ironman is a 10× duration gap where a bad inference mis-prescribes badly. Can be layered on later as an *initial guess* feeding the same default+override control. |
| **Reconcile Layer 0 so the two sheets agree** (add top-level PLA rows, or expand SDM/bridge to sub-formats) | Heaviest option; rewrites the reference-data contract. The sub-formats genuinely differ in phase load (that's why Sheet 5 splits them), so collapsing them to a single top-level PLA row would *lose curated signal*. Out of scope. |
| **Code-side default constant** | Bakes a curation decision into app code, against DB-is-source-of-truth. D2 puts it in Layer 0 instead. |

**Trade-off accepted under D1:** storing the resolved name means a later change to the Layer 0 *default* does not retro-update existing `race_events` rows. This is arguably correct — once an athlete has a concrete sub-format (default-applied or chosen), silently re-prescribing their plan because the platform default moved would be surprising. New events pick up the new default; existing events keep their stored sub-format until the athlete edits. Noted, not hidden.

---

## 4. Data / schema changes

### 4.1 New `layer0.sport_sub_format_map` (ETL-derived)

Derived during the Layer 0 ETL from the DISTINCT `phase_load_allocation.sport_name`s, split into `(parent, sub_format)` by the same parenthetical rule the app uses. Parents with a single name (no parenthetical) are **not** rows here — the absence of rows is what tells onboarding "no sub-format select needed."

Shape (final types in the implementation PR):

```
layer0.sport_sub_format_map(
  id            ...,
  parent_sport  text not null,   -- e.g. 'Triathlon'  (matches sport_discipline_bridge.framework_sport)
  sub_format_sport text not null,-- e.g. 'Triathlon (Standard / Olympic)'  (matches PLA.sport_name)
  is_default    boolean not null default false,
  display_label text,            -- optional athlete-facing short label, e.g. 'Standard / Olympic'
  etl_version   text not null,
  etl_run_at    timestamptz not null,
  superseded_at timestamptz
)
```

`validate_layer0` gate additions: (a) every `is_default` parent group has **exactly one** TRUE; (b) every `sub_format_sport` exists as a PLA `sport_name`; (c) every PLA sub-format parent is represented.

### 4.2 No `race_events` schema change

Under D1, `framework_sport` already holds the value we need; we change only what onboarding *writes* into it. The one-time backfill (D5) is a data migration, not a schema migration.

---

## 5. Layer 2A guard (D4) — proposed code shape

In `q_layer2a_discipline_classifier_payload`, after `raw_rows = _load_disciplines(...)`, before building disciplines:

```python
top_level_sport = _strip_sub_format(framework_sport)
raw_rows = _load_disciplines(db, top_level_sport, framework_sport)

# D-17 guard (#254): a known sub-format PARENT reaching us unstripped means
# onboarding stored the bare parent name — PLA is sub-format-keyed, so every
# phase_load band joined NULL. Surface loudly instead of emitting a silent
# no-volume plan.
if (
    framework_sport in _SUB_FORMAT_SPORTS                 # bare parent, not a sub-format
    and raw_rows                                          # SDM matched (disciplines exist)
    and all(r.get("base_pct_low") is None for r in raw_rows)  # but no PLA joined
):
    print(
        f"q_layer2a: framework_sport={framework_sport!r} is a sub-format parent "
        f"with zero PLA rows — onboarding did not resolve a sub-format (D-17/#254). "
        f"Flagging unresolved + HITL."
    )
    # → add an UnresolvedFlag(raw_input=framework_sport, suggested_match=<default>,
    #   severity='error') and force hitl_required=True in the payload assembly below.
```

The `_strip_sub_format` whitelist (`_SUB_FORMAT_SPORTS`) is **retained** — it remains the SDM-side mapping for correctly-resolved sub-format inputs. The guard is purely additive.

---

## 6. UX flow (§H.2)

1. Athlete picks **Race event type** (parent sport) — existing select, sourced from `sport_discipline_bridge` (top-level names).
2. If the picked parent has rows in `sport_sub_format_map`, a **Sub-format** select appears (client-side, from a parent→options JSON blob), pre-selected to `is_default`. Helper text in coaching voice, e.g. *"Pick the format that matches your race — it sets the phase-load model."*
3. On submit (two-column model, D1′): `framework_sport` = the parent value (unchanged); `sport_sub_format` = the sub-format select's value when shown, else NULL (→ default at compose time).
4. On profile edit of an existing event: both controls repopulate directly from the two stored columns — no name-parsing.
5. Parent change clears/re-defaults the sub-format select and fires the existing terrain-rescope + `framework_sport`-change invalidation already wired in `routes/onboarding.py` / `routes/race_events.py`; a `sport_sub_format`-only change fires the same invalidation (D6).

---

## 7. Spec amendments

§7.1–7.3 (Layer2A_Spec) **applied with slice 2** — worded "in progress" (guard shipped; capture remaining), not "closed", since capture lands in slice B. §7.4 (Onboarding spec) lands with slice B. The originally-proposed "Resolved/Closed" wording below is superseded by the actual in-progress wording in the spec.

### 7.1 `Layer2A_Spec.md` §5.1 — append after the existing v1-implementation paragraph

> **#254 resolution (2026-06-29):** onboarding now captures the sub-format up front via the **default + override** model (`Onboarding_SportSubFormat_D17_254_Design_v1.md`): the five sub-format parents (Triathlon, Skimo, LDC, Canoe/Kayak Marathon, OWMS) carry a Layer-0-curated default sub-format (`layer0.sport_sub_format_map.is_default`) pre-selected in the race-event form, which the athlete may override. `framework_sport` is therefore always stored as a real PLA `sport_name`; §5.2's strip-for-SDM logic is unchanged. A §5.x guard (D-17 guard) flags + HITL-gates any bare-parent value that still reaches 2A (legacy / regression), rather than emitting silent NULL bands.

### 7.2 `Layer2A_Spec.md` §6 — D-17 row Status edit

- old: `| Workaround in place; design owner is Layer 1 race-goal capture |`
- new: `| **Resolved #254 (2026-06-29):** onboarding captures sub-format (default+override, `sport_sub_format_map`); §5.1 strip retained for SDM; loud guard added. |`

### 7.3 `Layer2A_Spec.md` §12 — open item 2A-3 Status edit

- old: `| 2A-3 | D-17 resolution path for non-AR sports — sub-format selection in onboarding spec | Layer 1 race-goal capture | Tracked in `Project_Backlog.md` |`
- new: `| 2A-3 | D-17 resolution path for non-AR sports — sub-format selection in onboarding | Layer 1 | ✅ Closed #254 (2026-06-29) — `Onboarding_SportSubFormat_D17_254_Design_v1.md`. |`

### 7.4 `Athlete_Onboarding_Data_Spec_v6.md` §H.2 — add a field row (lands with slice B)

Add to the §H.2 field table a **Sport Sub-Format** row: closed enum per parent sport (from `layer0.sport_sub_format_map`), default = the parent's `is_default`, shown only for the five sub-format parents; stored in `race_events.sport_sub_format` (two-column model, D1′); composed with `framework_sport` to drive the Layer 2A phase-load joins. Distinguish explicitly from the existing `race_format` periodization enum.

---

## 8. Implementation slices

- **Slice 2 — Layer 2A guard (D4). ✅ SHIPPED** (commit on `claude/issue-254-cd81r3`): `q_layer2a` flags + HITL-gates a bare sub-format parent; tests; Layer2A_Spec §5.1/§6/§12 updated.
- **Slice A — Layer 0 table (D2). ✅ SHIPPED (code; awaiting gated apply):** migration `0031_sport_sub_format_map.sql` (CREATE + 17 seeded rows + DO-block verify), `validate_layer0` check `sport_sub_format_map` (+ test). **Needs the gated `layer0-apply` action (Andy one-tap) to land in prod Neon**, then a `layer0-redump` to fold into the baseline.
- **Slice B — serving/capture (D1′/D3/D5/D6). ⬜ NEXT:** add `race_events.sport_sub_format` column (`_PG_MIGRATIONS`, auto-applies on deploy) + backfill (D5); orchestrator compose of the Layer 2A input; the second select + parent→options JSON blob in the onboarding + profile templates; route submit wiring + invalidation (D6); `Athlete_Onboarding_Data_Spec_v6.md` §H.2 row (§7.4). Depends on slice A's table being applied (reads it for options/defaults).

Slice ordering note: slice B's serving compose can ship before slice A is *applied* only if it tolerates the table's absence (it won't until applied), so **apply slice A first**.

## 9. Resolved decisions (formerly open questions)

1. **Defaults (§2.1):** ✅ ratified 2026-06-29; seeded in 0031.
2. **Storage model:** ✅ **two-column (D1′)** — reversed from D1 after the bridge/terrain-consumer discovery (see §2 revision banner).
3. **Default-change propagation:** ✅ existing rows keep their stored `sport_sub_format` when the Layer-0 default later moves (athlete intent wins; new events pick up the new default).
4. **Sequencing:** ✅ guard shipped first (slice 2); Layer 0 (slice A) before serving/capture (slice B).

## 10. Gut check

- **Risk / what might be missing:** the `race_format` (periodization) vs. sport sub-format distinction is a real confusion trap — the spec amendment must call it out or someone will wire the wrong enum. The display-label/parse round-trip is the fiddliest bit (names contain `/` and parentheses); the whitelist parse must stay the single source of the split.
- **Best argument against this design:** D1 stores a derived value (resolved sub-format) rather than the athlete's raw intent (parent + chosen-or-default), so we can't later tell "default applied" from "explicitly chose the same as default," and a default move won't reach old rows. If we ever want analytics on default-acceptance or auto-re-prescription on default changes, the two-column model (open Q2) is better — but it costs a column, a migration, and an orchestrator resolution step for a benefit we don't need yet. Start with D1; the two-column model is a clean future migration if a consumer appears.
- **Scope honesty:** this closes the *capture* gap (the live bug) and the loud-failure gap. It does **not** add distance-based inference — deliberately deferred (§3) as a future enhancement that would feed the same control.
