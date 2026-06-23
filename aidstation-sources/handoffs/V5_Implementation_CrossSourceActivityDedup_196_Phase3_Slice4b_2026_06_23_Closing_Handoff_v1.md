# V5 Implementation — Cross-Source Activity Dedup + Merge (#196 Phase 3) — Slice 4b — Closing Handoff (2026-06-23)

**Branch:** `claude/cross-source-activity-dedup-7q7a3u` · **Suite:** 3536 passed / 30 skipped · **PR:** not yet opened — awaiting Andy's go (per the PR-gated operating flow).
**Predecessors:** the kickoff `handoffs/V5_CrossSourceActivityDedup_196_Phase3_Kickoff_2026_06_22_v1.md` (problem, slice sequence, Trigger-#3 gate), **Slice 1** (`…Slice1_2026_06_22…`, schema substrate + `started_at`), **Slice 2** (`…Slice2_2026_06_23…`, the clusterer), **Slice 3** (`…Slice3_2026_06_23…`, completeness scoring + `canonical_activity` materialization), **Slice 4a** (`…Slice4a_2026_06_23…`, the *math* consumer repoint + the `canonical_cardio_feed` view). This is **Slice 4b** — the *display* half: the summary/list surfaces that showed a cross-source ride N times.

---

## 1. The problem (one line)

One real-world activity reaching us via N connected providers (a Wahoo ride auto-forwarded to Strava) lands as **N `cardio_log` rows** (repro: user 1 rows 73 Wahoo + 74 Strava). Slices 1–3 group the duplicates into a cluster and merge each cluster into ONE best-of `canonical_activity` row; **Slice 4a** built the shared `canonical_cardio_feed` view and repointed the *math* consumers (training-load + compliance + coaching) so they count the ride once. **Slice 4b repoints the *display* consumers** so the UI *shows* the ride once.

## 2. The decisions (already ratified — Andy 2026-06-23, in Slice 4a's two AskUserQuestion rounds)

No new decisions this session — 4b executes the display half of the split Andy already ratified in 4a:

1. **One shared dedup read surface** (`canonical_cardio_feed`) — a display consumer swaps `FROM cardio_log` → `FROM canonical_cardio_feed` with no other change.
2. **The literal cardio-LOG list/edit pages keep showing every imported copy** (so a stray duplicate stays visible and deletable). Only the summary surfaces collapse to one best-of row.
3. **Split 4a math-first, 4b display-next** — 4b is this slice.

## 3. What Slice 4b shipped (4 substantive files: 2 code + 2 test)

- **`routes/connections.py`** — the Data-hub **Files** list:
  - **`_ACTIVITY_SQL`** (module constant) — `FROM cardio_log` → `FROM canonical_cardio_feed`. The Files list now shows a cross-source ride as one best-of row instead of N near-duplicates. Comment added (decision 2 spelled out: the literal log/CRUD pages stay raw).
  - the **activity-count** `SELECT COUNT(*) … FROM cardio_log` (in `_hub_context`) → `FROM canonical_cardio_feed`.
  - `_STRENGTH_SQL` + `_strength_row` untouched (strength lives in `training_sessions`/`training_log`, a different table — not part of the cardio dedup).
- **`routes/dashboard.py`** — `index()`:
  - **`cardio_total`** stat `SELECT COUNT(*) FROM cardio_log` → `FROM canonical_cardio_feed`.
  - the **recent-cardio strip** `SELECT date, activity, duration_min, distance_mi, avg_hr FROM cardio_log … LIMIT 5` → `FROM canonical_cardio_feed`.
  - the **unconditioned-cardio nudge** `FROM cardio_log cl LEFT JOIN conditions_log cond ON cond.cardio_log_id = cl.id` → `FROM canonical_cardio_feed cl …`. A cross-source ride now prompts for conditions **once** (against the feed's primary-copy `id`), not N times. Comment notes the `conditions_log` join resolves on that primary copy's id (see decision 2 in §4).
  - `training_total` (counts `training_log`) untouched — different table.
- **`tests/test_canonical_cardio_feed.py`** — added **`TestDisplayConsumersReadFeed`**: the Files list + count read the feed (and the old raw reads are gone); the dashboard's 3 cardio surfaces read the feed (`>= 3` occurrences + the `conditions_log` join intact + the strength count stays on `training_log`); and a regression guard that `routes/cardio.py` + `routes/training.py` **do NOT** reference `canonical_cardio_feed` (decision 2). Reads files as text → no Flask-app import (dodges the container's Neon-egress import hang), same posture as 4a.
- **`tests/test_redesign_connections_render.py`** — the Files-tab render smoke tests boot the real route against a **fake `_Conn`** that routes SQL by **substring** (`'cardio_log' in s`). `canonical_cardio_feed` does not contain the substring `cardio_log` → the Files queries fell through to the default cursor → `fetchone()` returned a row with no `'n'` key → `KeyError 'n'` on the 3 Files-tab tests. Fixed the fake to match **either** surface (`cardio_src = 'cardio_log' in s or 'canonical_cardio_feed' in s`; the `FROM` matcher likewise) so it tracks the live read. Docstring updated (`cardio_log (Files)` → `canonical_cardio_feed (Files)`).

## 4. Decisions baked in (review these)

1. **Display reads swap table only.** The view duplicates `cardio_log`'s column shape, so every repoint is a one-token `FROM` change; all the columns these queries select (`id, date, activity, activity_name, duration_min, distance_mi, avg_hr, max_hr, calories, garmin_activity_id, created_at`) exist in both UNION branches of the view. Verified against the view DDL before editing.
2. **Unconditioned-cardio join resolves on the primary copy's id.** The feed's clustered branch exposes the cluster's **primary** `cardio_log.id`. The `conditions_log` LEFT JOIN keys on `cardio_log_id = cl.id`, so a conditions entry logged against the **primary** copy resolves; one logged only against a **secondary** copy would not (the ride would still read as "needs conditions"). Acceptable + consistent with the Slice-4a "primary is the richest copy" stance — and this surface was explicitly named a 4b target in the 4a handoff §6. The win (one prompt per real ride instead of N) is the point of the repoint.
3. **The literal log/CRUD pages stay raw — guarded by a test.** `routes/cardio.py` + `routes/training.py` list/edit pages keep reading raw `cardio_log` (decision 2). Added an explicit `assert "canonical_cardio_feed" not in src` regression guard so a future editor doesn't "finish the job" and break the deliberate behavior.
4. **The render-test fake had to move with the surface.** The fake `_Conn` is a substring router, not a real DB — repointing the route without updating the fake silently mis-routed the query. This is the display analog of why 4a's math repoints needed no fixture change (those consumers aren't exercised by a substring-router fake). Not a production bug.

## 5. Tests + verification

- `SECRET_KEY=x DATABASE_URL='postgresql://u:p@127.0.0.1:1/db?connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q` → **3536 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217, unrelated). Touched-file run (front-load a `test_layer4_*` to dodge the isolated-collection circular-import quirk): `pytest tests/test_layer4_plan_create.py tests/test_canonical_cardio_feed.py tests/test_layer3a_integration.py -q` → **173 passed** (+3 new display-consumer tests).
- **No DDL this slice** — the `canonical_cardio_feed` view shipped in Slice 4a (additive / `CREATE OR REPLACE` / public-schema → auto-applies on each Vercel deploy). **No Neon apply owed.**
- **LIVE-VERIFY owed (Andy-action — container can't reach Neon; folds into Slice 4a's verify):** with a cross-source duplicate present (the rows-73-Wahoo/74-Strava repro), confirm the **Data-hub Files list**, the dashboard **`cardio_total` stat + recent-cardio strip**, and the **unconditioned-cardio nudge** each show the ride **ONCE** (not twice), and that an unclustered/legacy (`cluster_id IS NULL`) row still surfaces in all three. The unit tests prove the consumers *read the feed*; only prod proves the view *collapses* correctly.

## 6. NEXT — Phase 3 is complete; the #196 epic stays open for Phases 4–5

Slice 4 is done (4a math + 4b display), which completes the kickoff's **Phase 3** (activity cross-source dedup + merge + repoint the consumers at the canonical record). A cross-source ride is now counted and shown once across every summary/coaching/load/compliance/display surface; only the deliberately-raw log/CRUD pages still show every copy (by design).

**#196 is the 5-phase epic** (Phase 1 Garmin metrics ingestion → Phase 5 multi-service expansion) — it **stays OPEN** for Phases 4–5. What's left *within Phase 3*, both optional / gated:
- **Slice 5 (optional)** — conflict-surfacing UI: show the athlete when sources materially disagree on a merged field, or merge silently? The `canonical_activity_field_provenance` table already records *which* source won each field. Its own ≤5-file slice; needs an AskUserQuestion design gate first (surface-vs-silent is the open question).
- **#920-gated repoint** — `coaching._get_performance_delta` is Postgres-broken (SQLite `GROUP_CONCAT` + non-aggregated `GROUP BY`); when #920 is fixed, move its compliance `LEFT JOIN cardio_log cl ON cl.plan_item_id = pi.id` to the feed.

**Recommendation:** tick Phase 3 on the #196 roadmap (comment the 4a+4b landing) and keep the epic open for Phase 4/5; don't close #196. Track Slice 5 as a fresh optional issue if/when Andy wants the conflict UI; the #920 repoint rides #920.

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this Slice 4b). 3. `CARRY_FORWARD.md` → *"#196 cross-source activity dedup"*. 4. This handoff + Slice 4a + Slice 3 + Slice 2 + Slice 1 + the kickoff. 5. `routes/connections.py` `_ACTIVITY_SQL` + the Files `COUNT(*)`; `routes/dashboard.py` `cardio_total` / recent-cardio / unconditioned-cardio (repointed); `init_db.py` `canonical_cardio_feed` view (the shared surface). 6. `./scripts/verify-handoff.sh`.

## 7. Open questions (carry from the epic / kickoff §9)
- **Conflict surfacing (Slice 5, optional)** — show the athlete when sources materially disagree on a merged field, or merge silently? Provenance is already recorded.
- **#920** — `coaching._get_performance_delta` Postgres incompatibility; fix, then repoint its compliance JOIN at the feed.
- _(Resolved Slice 4a: shared view vs per-consumer edits → shared `canonical_cardio_feed` view; log list/edit pages stay raw; 4a-math / 4b-display split.)_

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Files list repoint | `routes/connections.py` | `_ACTIVITY_SQL` reads `FROM canonical_cardio_feed WHERE user_id = ?`; the Files count reads `SELECT COUNT(*) AS n FROM canonical_cardio_feed` (grep; old `FROM cardio_log WHERE user_id` / `COUNT(*) AS n FROM cardio_log` gone) |
| Dashboard repoints | `routes/dashboard.py` | `cardio_total` `SELECT COUNT(*) FROM canonical_cardio_feed`; recent-cardio strip `FROM canonical_cardio_feed … LIMIT 5`; unconditioned nudge `FROM canonical_cardio_feed cl LEFT JOIN conditions_log cond ON cond.cardio_log_id = cl.id` (grep — `>=3` feed hits, 0 raw `FROM cardio_log`) |
| Log pages stay raw | `routes/cardio.py`, `routes/training.py` | `canonical_cardio_feed` absent (grep — 0 hits each); raw `cardio_log` reads intact (decision 2) |
| Display tests | `tests/test_canonical_cardio_feed.py` | `TestDisplayConsumersReadFeed` (Files list+count, dashboard ×3, log-pages-stay-raw) |
| Render fake updated | `tests/test_redesign_connections_render.py` | `_Conn.execute` matches `'canonical_cardio_feed' in s` for both the COUNT + FROM branches |
| Suite | — | `… pytest tests/ -q` → 3536 passed / 30 skipped |
| Issue | #196 | comment: Phase 3 Slice 4b (display repoint via `canonical_cardio_feed`) shipped on `claude/cross-source-activity-dedup-7q7a3u`; **Phase 3 complete** (math 4a + display 4b) — epic stays OPEN for Phases 4–5; optional Slice 5 + #920-gated repoint are the only Phase-3 leftovers |
