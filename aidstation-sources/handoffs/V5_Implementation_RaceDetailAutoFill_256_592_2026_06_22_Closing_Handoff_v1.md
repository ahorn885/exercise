# V5 Implementation — Race-detail auto-fill (#256 + #592, folded) — Closing Handoff

**Date:** 2026-06-22
**Branch:** `claude/youthful-feynman-93w8zl`
**PRs:** #863 (design + prompt body for #256), #864 (#592 prompt body), #871 (backend Slices 1-3) — all **MERGED**; the UI (Slice 4) PR #872 is open + auto-merge.
**Scope:** the folded #256 (paste a race URL → LLM pre-fills the race-entry form) + #592 (race-location → terrain inference, now the subordinate fallback). Design-first specs + both prompt bodies were written and signed off this same session-cluster, then built in 4 slices.

---

## 1. What shipped

Per Andy's fold: **website parse primary; location inference fills terrain only on the gap; weather normals always from the location.**

- **Slice 1 — `race_url_parser.py`** (#256). `fetch_and_reduce(url)`: best-effort `requests.get` + timeout / size-cap / content-type + public-host **SSRF** guards, then stdlib HTML→visible-text (no new dep). `parse_race_url(input)`: single forced tool-use (`record_race_url_parse`) via the shared `invoke_tool_call` harness (Sonnet 4.6 / temp 0 / thinking off), then **per-field drop-invalid** validation. Never-fabricate → null; **distance is a menu** (never auto-set); terrain reuses Layer-2B vocab + per-group [80,120] pct-sum + the **`stated/estimated` coarse-estimate basis** flag. `tests/test_race_url_parser.py` (31).
- **Slice 2 — `race_terrain_inference.py`** (#592, subordinate). `infer_terrain(input)`: single forced tool-use (`record_race_terrain_inference`); per-discipline coarse breakdown, honest confidence, **no silent repair** (off-vocab / unknown-discipline / pct-sum-out-of-bounds RAISES → the empty editor). Season phrasing (hemisphere-aware); `as_race_terrain()` maps to the `race_terrain` JSONB shape. `tests/test_race_terrain_inference.py` (14).
- **Slice 3 — endpoints in `routes/race_events.py`.** `GET /profile/race-events/parse-url?url=` + `GET …/infer-terrain?lat=&lng=&…` (mirror `locale_search`: auth-gated, CSRF-free, best-effort). Testable cores `run_url_parse` / `run_terrain_inference` (helper-level pytest per this module's convention). `infer-terrain` also surfaces the existing `get_expected_conditions` nudge. Loaders `_terrain_vocab_entries` + `_all_disciplines`. `tests/test_race_events_autofill.py` (13).
- **Slice 4 — UI: `templates/_race_url_autofill.html`** on both `onboarding/target_race.html` + `profile/race_event_edit.html`. **"Fetch details from URL"** → pre-fills *empty* fields only, the **"which distance?" chooser**, routes `location_text` into the Mapbox picker, pre-fills page-terrain. The **#592 fallback AUTO-FIRES** (Andy 2026-06-22): in-page location-confirm + on load when an existing race has coords + empty terrain. Precedence: never when the page already supplied terrain. Script defers wiring to `DOMContentLoaded` (partial sits mid-form). Refreshed the stale "future site-parse" helptext.

Design artifacts (merged earlier this cluster): `designs/Race_URL_Parser_Spec_v1.md`, `designs/Race_Location_Terrain_Inference_Spec_v2.md` (v1 archived), `prompts/RaceURLParser_v1.md`, `prompts/RaceTerrainInference_v1.md`. Persistence split to **#856**.

## 2. Key decisions (Andy)

- Fold #256 + #592 (website primary, location subordinate terrain backfill).
- Distance athlete-selected, never inferred (editable field + chooser).
- Terrain proportions **coarse, flagged estimates** (`terrain_pct_basis`); #592 always estimated (geography, not a course map).
- Persistence → #856; this slice transient.
- Prompt bodies signed off 2026-06-22.
- #592 fallback **auto-fires** (was an explicit button in the first draft).
- §12 defaults: keep discipline extraction (miss→defaults); stdlib HTML-reduce; pre-fill empty-only; no dedup cache.

## 3. Tests / verification

Full suite **3269 passed / 30 skipped** (the 4 new suites inject LLM callers / fetcher / weather — no network/API). JS passes `node --check`; both templates render (redesign full-render tests green); `import app` registers both routes.

## 4. LIVE-VERIFY owed (Andy-action — see CARRY_FORWARD)

Interactive JS + the live LLM path are manual-walkthrough (the jsdom harness covers `static/app.js` only). On a real race page: Fetch details → fields pre-fill + chooser + location candidates; confirm a location with empty terrain → terrain + conditions auto-fire; a course-describing page pre-fills terrain directly (then no #592 fire — precedence); a JS-only/unreadable page degrades to a hint.

## 5. Follow-ups

- **No backend dedup cache** — auto-fire re-fires the LLM on each load of a coords-without-terrain race; add the input-hash dedup (spec §6) or a throttle if cost/latency bites.
- **#856** — the crowd repeated-race profile store (split-out persistence).
- Spec'd open items: per-event terrain (RUP-4), PDF-flyer parse, a Haiku cost-down, a smoke-eval harness.

## 6. Operating notes for next session

### 6.3 Session-start reads (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last shipped = this (#256/#592 race-detail auto-fill).
3. `CARRY_FORWARD.md` — the `## #256/#592 race-detail auto-fill` carry-section (LIVE-VERIFY + follow-ups).
4. This handoff.
5. `./scripts/verify-handoff.sh` — the anchor sweep.

## 7. Issues touched

- **#256** — built + shipped; commented + **closed completed**.
- **#592** — built + shipped (subordinate fallback); commented + **closed completed**.
- **#856** — filed this cluster (crowd store); stays open (future).

## 8. §8 anchor table (Rule #9 sweep input)

| File | Anchor string | Check |
|---|---|---|
| `race_url_parser.py` | `def parse_race_url(` + `def fetch_and_reduce(` | exists |
| `race_terrain_inference.py` | `def infer_terrain(` + `class TerrainInferenceError` | exists |
| `routes/race_events.py` | `def run_url_parse(` + `def run_terrain_inference(` + `@bp.route('/parse-url'` + `@bp.route('/infer-terrain'` | grep |
| `templates/_race_url_autofill.html` | `rud_fetch_btn` + `fireInferTerrain` | exists |
| `templates/onboarding/target_race.html` / `profile/race_event_edit.html` | `_race_url_autofill.html` include | grep |
| `prompts/RaceURLParser_v1.md` / `prompts/RaceTerrainInference_v1.md` | `record_race_url_parse` / `record_race_terrain_inference` | exists |
| `tests/test_race_url_parser.py` / `test_race_terrain_inference.py` / `test_race_events_autofill.py` | new suites | `pytest` |
