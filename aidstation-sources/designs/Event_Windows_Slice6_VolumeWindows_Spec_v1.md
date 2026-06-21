# Event Windows — Slice 6: reduced-volume / no-training (in-transit) windows — Build Spec v1

**Parent design:** `designs/Event_Windows_Design_v1.md` (F9 deferred the `reduced_volume` flag to its own issue). **This is the build spec for GitHub [#593](https://github.com/ahorn885/exercise/issues/593)** — the deferred fourth override family: a *volume* override (the athlete is **in transit** — flying, long drive — and trains **less or not at all**), as opposed to the three existing *feasibility* overrides (`indoor_only`, `locale_unavailable`, `away`).
**Status:** **DESIGN-FIRST — NOT BUILT.** Scoped per Andy 2026-06-21 ("lets scope it — both routes (reduced and no training); we need to use the same ruleset we use now to try and prevent failures — changing formats, reallocating, etc.; if those can't be done we probably just drop what can't be done"). Hits **Stop-and-ask Trigger #3** (new override type + cross-layer surface: schema + grid + cache hash). DDL owed Andy's hands / `layer0-apply`-adjacent. No build until §11 sign-off.
**Date:** 2026-06-21

---

## 1. Purpose + scope

Let the athlete declare date-bounded **volume windows** — travel days where they train less or not at all — and have plan-gen scale those days down (or out) rather than placing a normal session on them:
- **`reduced_volume`** — the day holds only a reduced load (short/easy work; default ~50% capacity, see §3).
- **`no_training`** — the day holds nothing (capacity 0).

The athlete's request (Andy, on #593): on a travel day they "train less or not at all"; the plan should scale the day down so they don't have to manually skip it.

**In scope:** two new `override_type` values on the existing `athlete_event_windows` table; a **deterministic per-week trim-to-fit** step that drops day-capacity for the windowed dates and reuses the *existing* reallocate → reformat → drop ruleset to absorb or shed the freed load; the synthesis placement directive for the affected week; the cache hash (already folds new window fields); Rule #15 logging.

**Out of scope:** new locations, craft, or terrain (those are Slices 2–4); changing *what* is feasible (that's the feasibility overrides — a volume window is orthogonal and **unions** with them, §4); LLM-decided volume (counts stay deterministic, §2).

**Success criteria:**
- (a) No volume windows → byte-identical plans (regression).
- (b) A 1-day `no_training` window mid-week where the week has slack → that day is empty; its session **reallocates** to an open day; weekly count conserved (no drop).
- (c) A `no_training` window on a day where the week is already full → the lowest-priority session for that week is **deterministically dropped** (logged); key quality/long sessions preserved.
- (d) A `reduced_volume` window → the day carries at most a short/easy session; overflow reallocates-or-drops by the same rule.
- (e) Adding/moving a volume window invalidates only overlapping synthesis.

---

## 2. Boundaries

- **Counts/volume stay deterministic.** Consistent with the whole architecture (Slice 1 §2, `session_grid.py`), the **deterministic** layer decides how many sessions the windowed week can hold and which to drop; the **LLM only places** the surviving sessions on the open days. No probabilistic volume decision is added.
- **A volume window does not change *feasibility*.** It changes *how much*, not *what kind*. On a day that is both `no_training` and (say) `away`, the volume override wins for that day (0 capacity → the away feasibility for that day is simply unused). The two override families compose by **union** (§4), reusing the Slice-1 overlapping-windows union path.
- **Reuse the existing failure-prevention ruleset (Andy's ruling).** The freed load from a windowed day is handled by, in order: (1) **reallocate** to another day in the week (the LLM's existing placement freedom); (2) **reformat** (the existing cascade's proxy/indoor/strength substitution + intensity modulation — a hard session becomes easy/shorter); (3) **drop** what still can't fit. Drop is the last resort, mirroring the cascade's terminal `REALLOCATE`-tier ("don't prescribe") semantics in `session_feasibility.py`.

---

## 3. Data model (DDL — owed Andy's hands / `layer0-apply`-adjacent)

Extend `athlete_event_windows` (idempotent `_PG_MIGRATIONS` ALTER), no new table:

| Column | Type | Notes |
|---|---|---|
| `override_type` | TEXT | gains `reduced_volume` \| `no_training` (now: `indoor_only` \| `locale_unavailable` \| `away` \| `reduced_volume` \| `no_training`) |
| `volume_pct` | NUMERIC NULL | the retained fraction for `reduced_volume` (0 < pct < 1). NULL for every other type; defaulted in app code when unset (proposed default **0.5**). `no_training` is `volume_pct = 0` semantically — stored as the discrete type, not pct=0, so it reads cleanly. |

- `OVERRIDE_TYPES` (`athlete_event_windows_repo.py:39`) gains the two values; `add_event_window` validation (`athlete_event_windows_repo.py:150`) requires `volume_pct ∈ (0,1)` iff `reduced_volume`, and **clears all locale fields** (`unavailable_locale`, `away_locale`, `brought_craft`) for both new types (they carry no location — mirrors the `indoor_only` clear at `athlete_event_windows_repo.py:186`).
- No CHECK constraint (project no-CHECK convention); enforced in app code.

**Knob question (open item §11):** whether `reduced_volume` needs a stored per-window `volume_pct` at all, or a single fixed "reduced = at most one short/easy session" rule is enough. The fixed rule is simpler (no knob — "Simplicity first") and covers the stated use case; the column is only worth it if Andy wants graded travel days. **Recommendation: ship the fixed rule first (no `volume_pct` column), add the column later iff wanted.** Spec carries both so the decision is one edit.

---

## 4. Resolution model — a deterministic per-week capacity trim, then existing placement

This is the **first override that touches counts** (Slices 1–2 deliberately left counts on the home environment — Slice 1 §4 ¶3). The feasibility cascade is untouched; the new element is a **per-day capacity ceiling** feeding a **deterministic trim-to-fit** in the weekly grid.

1. **Load + union the windows for the plan span** (existing `_build_event_window_overlay`, `orchestrator.py:770`). Volume windows are collected alongside the feasibility windows; on overlapping dates the union carries *both* a feasibility reduction (from indoor/locale/away) *and* a capacity reduction (from reduced/no-training). Reuses the Slice-1 overlapping-windows union edge case.
2. **Per affected week, compute day capacity:** each `no_training` date → capacity 0; each `reduced_volume` date → capacity = `volume_pct` (or the fixed "≤1 short/easy session" rule); every other date → full. The week's **trainable-day budget** is the sum.
3. **Trim-to-fit (the one new deterministic step).** The grid (`session_grid._allocate_discipline`, `session_grid.py:383`) still produces the week's per-discipline counts against home. If the week's total session count exceeds the trainable-day budget:
   - **First** rely on reallocation — the surviving days absorb the freed sessions (the LLM already places sessions on days; no count change). Most short windows resolve here (success criterion (b)).
   - **If it still doesn't fit**, deterministically **trim** in a fixed priority order until it fits: **recovery/mobility first → easy/aerobic volume cardio → secondary (lowest-2A-weight) disciplines**, always **preserving the phase's key sessions** (the long session and the phase's hard/quality sessions, per `_intensity_mix` / `_type_sessions`, `session_grid.py:430`). This is a count reduction — the "trains less" outcome the athlete asked for. Each drop is logged (§7).
   - **Reformat is automatic** — a session that survives but lands on a `reduced_volume` day composes at that day's reduced tier through the existing cascade/intensity machinery; no bespoke logic.
4. **Synthesis places the surviving set.** `per_phase._format_event_window_overlay` (`per_phase.py:1612`) renders a volume directive for the windowed dates: *"Days X–Y: in-transit — no training | reduced volume (≤ short/easy). Place the week's remaining sessions on the open days; the deterministic grid has already trimmed the week to fit."* The LLM places (existing job); it never decides what to drop.

**Why this stays deterministic.** The drop set is computed by the grid in a fixed priority order — the LLM is told the trimmed counts, exactly as it's told untrimmed counts today. Nothing probabilistic is introduced; this is the same "resolver decides which/how-many, LLM places" contract as Slice 1 (§4 "Why no overflow arithmetic is needed"), extended from *feasibility tiers* to *capacity*.

**Accepted limitation (mirrors Slice 1 §4 ¶5).** A trimmed week falls **below** the validator's phase volume band (`validator.phase_week_volume_bands_hours`). For genuine travel weeks that's correct (the athlete *is* training less), and the band rule is advisory. The clean fix — feed the validator the windowed capacity for weeks a volume window covers so it bands against reduced capacity — is deferred to when it bites; flagged in §11.

---

## 5. Change surface (≤5 substantive files)

1. **`athlete_event_windows_repo.py`** — add the two `override_type` values + `volume_pct` validation/clearing.
2. **`init_db.py`** — idempotent ALTER adding `volume_pct` (only if §3 keeps the column; bookkeeping-adjacent).
3. **`layer4/session_grid.py`** — the per-week trainable-day budget + deterministic trim-to-fit in fixed priority order. **The one genuinely new arithmetic** (small; sits beside `_allocate_discipline`).
4. **`layer4/orchestrator.py`** — collect volume windows in `_build_event_window_overlay`; pass the per-week capacity into the grid call. Rule #15 log of the capacity + the drop set.
5. **`layer4/per_phase.py`** — render the volume directive in `_format_event_window_overlay` (Trigger-#1-adjacent wording; the overlay block already exists from Slice 1, so this is an added clause, not a new prompt — see §11).
- **Caching:** `compute_event_windows_hash` (`hashing.py:186`) already digests all window fields generically; adding `volume_pct` to the flattened dict is one line and folds into both plan keys automatically (no new hash).
- **Tests** (not counted): extend `tests/test_layer4_event_windows.py` + `tests/test_athlete_event_windows_repo.py` with the four success-criterion scenarios.

---

## 6. Caching

`compute_event_windows_hash` already keys on `override_type + dates (+ all window fields)`; the two new types and `volume_pct` ride the existing digest → a volume-window edit invalidates exactly the overlapping synthesis (success criterion (e)); no-windows stays byte-identical (success criterion (a)).

---

## 7. Rule #15 logging

Per windowed week, print inputs + decision:
`volume_window_trim: <phase>:w<W> dates=<range> type=<reduced_volume:pct|no_training> day_budget=<n> week_count=<m> dropped=[<session ids/disciplines, priority-ordered>] reallocated=<k>` — naming the capacity, the pre-trim count, and **exactly which sessions were dropped vs reallocated**, so a surprising trimmed week is diagnosable from logs alone (Rule #15). A no-drop reallocation logs `dropped=[]`.

---

## 8. Edge cases
- **Volume window over a day with slack in the week** → no drop; pure reallocation (criterion (b)).
- **`no_training` covering a whole week** → day budget 0 → every session trims; the week becomes a full rest week (logged). Validator under-volume is expected (§4 limitation).
- **`reduced_volume` + `indoor_only` same day** → union: capacity reduced *and* feasibility reduced; the surviving short/easy session composes at the indoor tier. No new logic (union of the two override paths).
- **`reduced_volume` + `away` same day** → union: the day is capped low; the away environment is simply mostly unused that day. (Common real case: the *travel* day is `no_training`/`reduced`, the *arrival* days are `away`.)
- **Window outside the plan span** → ignored (hash unaffected) — existing Slice-1 behavior.
- **Trim would drop a key session** (the only long session lands on the only open day and the day is also `reduced_volume`) → preserve the key session, reformat it down (shorter), drop the lower-priority sessions first; log it.

---

## 9. Test scenarios
1. No volume windows → identical grid + cache key. *Regression.*
2. `no_training` 1 day, week has slack → that day empty, session reallocated, weekly count unchanged, `dropped=[]`.
3. `no_training` 1 day, week full → lowest-priority session dropped (recovery/easy first), key sessions preserved, drop logged.
4. `reduced_volume` (0.5) 1 day → day holds ≤ a short/easy session; overflow reallocates-or-drops by the same rule.
5. `no_training` whole week → full rest week; validator under-volume tolerated; logged.
6. `reduced_volume` unioned with `indoor_only` same dates → both reductions apply; surviving session composes indoor.
7. Cache: add/move/delete a volume window → only overlapping weeks' synthesis recomputes.
8. Rule #15 `volume_window_trim` line present + correct (capacity, pre-trim count, drop/realloc set).

---

## 10. Why this is small
The cascade, the overlay rendering, the union path, the hash, and the LLM placement contract are **all reused from Slices 1–2**. The only genuinely new code is: two enum values + an optional column (§3), and a **deterministic per-week trim-to-fit in a fixed priority order** (§4 step 3, in `session_grid.py`). That single arithmetic is the entire novel surface — everything else is wiring volume windows into machinery that already exists.

---

## 11. Open items / sign-off
- **`volume_pct` knob — DECISION OWED (Andy).** Ship the fixed "reduced = ≤1 short/easy session" rule (no column, simpler), or store a graded per-window `volume_pct`? **Recommendation: fixed rule first.** (§3)
- **Trip priority order — CONFIRM (Andy).** The proposed drop order is recovery/mobility → easy/aerobic volume → lowest-2A-weight disciplines, preserving long + quality. Confirm this matches how you'd shed a travel week. (§4 step 3)
- **Trigger #1 wording — OWED at build.** The volume directive added to the existing event-window overlay block (`per_phase._format_event_window_overlay`). It extends a shipped prompt rather than authoring a new one, but the clause wording still needs sign-off at build (matches Slice 1's Trigger-#1 treatment). (§5.5)
- **Validator band under windowed weeks — accepted limitation now; clean fix deferred** (feed the validator the windowed capacity for covered weeks). (§4)
- **DDL apply** — via `init_db._PG_MIGRATIONS` ALTER, applied on Neon (owed Andy's hands / `layer0-apply`-adjacent), iff §3 keeps `volume_pct`.

## 12. Gut check
- **Best argument against building it:** Andy deferred this for a reason — "the athlete can figure that out themselves." A travel day is trivially handled by the athlete skipping a session; the deterministic trim only earns its keep if travel is frequent enough that manual skipping is annoying *and* the dropped-session priority is something the athlete trusts the system to get right. If either is shaky, this stays parked.
- **Biggest risk:** the **drop priority order** is a coaching judgment, not a mechanical one — dropping the wrong session (e.g. the week's only long aerobic run because a quality session "outranks" it on a key endurance week) is worse than the athlete skipping manually. The fixed order in §4 needs Andy's confirmation, and Rule #15 logging is what makes a wrong drop catchable.
- **What might be missing:** interaction with the **refresh** path — if the athlete logs a travel day *after* the plan is built, the volume-window hash change should trigger a T1/T2 refresh of the affected week (falls out of the existing window→hash→refresh loop, F6, once volume windows feed the hash — but worth a refresh-path test).
- **What's genuinely clean:** modeling volume as a separate `override_type` that **unions** with the feasibility overrides (rather than a flag on them) means travel-day + away/indoor compose for free on the existing overlap path — no combinatorial new code.
