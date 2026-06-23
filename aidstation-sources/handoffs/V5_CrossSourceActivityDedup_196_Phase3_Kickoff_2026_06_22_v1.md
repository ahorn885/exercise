# V5 Kickoff — Cross-Source Activity Dedup + Merge (#196 Phase 3)

**Date:** 2026-06-22
**Status of #196:** epic open; Phases 1–2 (Garmin metrics, canonical daily-wellness) per the epic body. **Phase 3 (activity cross-source dedup + merge) is NOT started** — this handoff is its starting point.
**Trigger:** surfaced live during Wahoo go-live verification (#681). With both Wahoo and Strava connected, one ride produced **two `cardio_log` rows**. Repro + design notes: [#196 comment 2026-06-22](https://github.com/ahorn885/exercise/issues/196#issuecomment-4770707395).
**Predecessor work this session:** PR #841 (Wahoo OAuth redirect_uri + legible callback errors) and PR #896 (Wahoo nested-payload ingest fix) — both merged. Neither touches dedup; they're why the duplicate became visible.

---

## 1. The problem, concretely

A single recorded activity becomes N `cardio_log` rows when it reaches us via N connected providers. Verified repro (user `1`, 2026-06-22):

| `cardio_log.id` | source | dedup id | sport / name |
|---|---|---|---|
| 73 | Wahoo webhook | `wahoo_workout_id = 417773586` | cycling, "Indoor Cycling test" |
| 74 | Strava webhook | `strava_activity_id = 19018321756` | cycling, "Indoor Cycling test" |

Same ride; both `signature_ok`; activity `started_at` ~06:28:56Z for both. A Wahoo head unit that auto-forwards to Strava (very common) doubles **every** ride for any athlete who connects both.

## 2. Where dedup stands today (what to build ON, not break)

- `cardio_log` carries **per-source** dedup columns, each with a partial-unique index `(user_id, <col>) WHERE <col> IS NOT NULL` (`init_db.py`):
  `garmin_activity_id` (also holds manual-upload `fit:` content hashes), `strava_activity_id`, `wahoo_workout_id`, `polar_exercise_id`, `coros_label_id`, `rwgps_trip_id`.
- **Per-source idempotency works and is proven** — in the repro Wahoo double-sent the `workout_summary` and the second collapsed to one row on `wahoo_workout_id` (the `SELECT … SKIP already-imported` guard in `routes/wahoo.py:_ingest_workout_summary` + the unique index). **Keep these intact** — Phase 3 adds a layer *above* per-source dedup, it does not replace it.
- **No cross-source matching exists.** Nothing recognizes that row 73 and row 74 are the same real-world activity.
- `provider_raw_record` already stores per-source raw corroboration (`provider`, `data_type`, `external_id`) — useful gap-fill/provenance source for the merge.

**Write paths (all call `routes/garmin.py:_bulk_insert_cardio`, `source=…`):** `routes/wahoo.py`, `routes/strava_ingest.py`, `routes/whoop_ingest.py` (workout→raw only today), `routes/oura.py`, `routes/polar_ingest.py`, `routes/coros_ingest.py`, `routes/ride_with_gps.py`, and the manual uploader (`routes/garmin.py:import_bulk` via `_SOURCE_MAP`).

## 3. Session-start read order (Rule #13)

1. `CLAUDE.md` — stable rules (note **Trigger #3** applies here — see §6)
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. This handoff
5. `./scripts/verify-handoff.sh`
6. Then read: the **#196 epic body** ("Phase 3 — Activity cross-source dedup + merge" + the merge/dedup model + design defaults), the **#196 2026-06-22 comment** (repro), `init_db.py` (the `cardio_log_*_uidx` block), `routes/garmin.py:_bulk_insert_cardio` + `_SOURCE_MAP`, and one provider ingest end-to-end (`routes/wahoo.py` is the cleanest).

**Env note (verified this session):** the container reaches only a cold/blocked Neon, so `import routes.auth` (pulled in by every `routes/*` ingest module) hangs at import — it transitively does `import app` → `init_db.init_postgres()` which blocks on `psycopg2.connect`. Run pytest with a fast-failing DB so the import proceeds:
`SECRET_KEY=x DATABASE_URL='postgresql://u:p@127.0.0.1:1/db?connect_timeout=2' /tmp/venv/bin/python -m pytest tests/ -q`
(`pip install -r requirements.txt pytest` first — main's MFA work added `pyotp`/`qrcode`.) Isolated single-file collection also hits a pre-existing layer3a↔layer4 circular import; run the broader suite or the targeted provider tests (`test_wahoo_ingest`, `test_provider_cardio_resolve`, `test_strava_ingest`).

## 4. The design (ratified defaults already in the #196 epic — don't re-derive)

The epic locked these; Phase 3 implements them:
- **Fingerprint** groups duplicates across sources: `(sport-class, start-time bucket ±min, duration ±%, distance ±%)`.
- **Primary = completeness score**, not a fixed device order (power? HR? GPS? cadence? sample density? elevation?). Static source order is **only a tiebreaker**.
- **Canonical = primary's fields + gap-fill from secondaries** (e.g. a Garmin ride missing power gets power from the Wahoo copy).
- **Manual override always wins.**
- **Per-field provenance retained** ("HR from Garmin, power from Wahoo").
- Storage default: a **link column + materialized merged record on the existing `cardio_log`**, NOT a from-scratch activities table (avoids migrating every consumer at once).

## 5. Proposed slices (sequence; each its own PR under the 5-file ceiling)

**Slice 1 — schema + clustering key (Trigger #3 — ratify DDL with Andy FIRST, see §6).**
Add a nullable cluster key to `cardio_log` (rows in one real-world activity share it) + a `is_canonical` / primary flag. Per-source `*_uidx` indexes stay. No consumer change yet — just populate the key.

**Slice 2 — the clusterer (the real matching logic).** A pure function `cluster_activity(db, user_id, new_row) -> cluster_id` called by `_bulk_insert_cardio` (and the manual path) right after insert: compute the fingerprint, find existing same-user rows within tolerance, attach to an existing cluster or open a new one. Must be **idempotent** and **re-entrant** (re-runs and late arrivals don't fork clusters). Instrument per Rule #15 (log the inputs + the match/no-match decision + the cluster id).

**Slice 3 — completeness scoring + canonical materialization.** Score each row in a cluster, pick primary, gap-fill from secondaries, write the merged/`is_canonical` record + per-field provenance. Re-materialize whenever a cluster gains/loses a member (late Strava/RWGPS arrival).

**Slice 4 — repoint consumers at the canonical record.** The readers that must show "one activity, best-of" rather than N rows: `routes/connections.py` (`_ACTIVITY_SQL` Files list + the Manual/Synced chip), `routes/dashboard.py`, `routes/cardio.py`, `routes/training.py`, `routes/plans.py` (plan-match/compliance), `layer3a/builder.py` + `layer3a/integration.py` (recent-activity → athlete state), `layer4/context.py` (plan-gen context), `coaching.py`, `routes/profile_extractors.py` (HRmax-from-cardio prefill). Filter to `is_canonical` (or join through the cluster) so training-load/compliance count the ride **once**.

**Slice 5 (optional) — conflict surfacing UI.** Only if §11 open question lands on "show disagreement."

## 6. Stop-and-ask — Trigger #3 (cross-layer schema change)

`cardio_log` is read by Layers 3A and 4; a new cluster/canonical/provenance shape is an **inter-layer contract change → Trigger #3. Ratify the DDL with Andy before building Slice 1.** Bring options + a recommendation:

- **(A) Self-clustering on `cardio_log`:** add `activity_cluster_id TEXT` + `is_canonical BOOL`. Cheapest; merged record is just the canonical row (its fields gap-filled in place). Provenance via a sibling `cardio_field_provenance` table — **reuses the exact pattern already in `athlete_profile_field_provenance`** (precedent worth leaning on).
- **(B) Separate `activity_clusters` + `canonical_activity` tables**, `cardio_log.cluster_id` FK. Cleaner separation; more migration + more consumer rewiring.
- **Recommendation:** **(A)** — matches the epic's "link column + materialized record on existing tables" default and the established provenance pattern; least consumer churn for a v1 with one test athlete.
- **Gut check / what might bite:** late arrivals (RWGPS is **cron-deferred up to 24h**, Strava can lag minutes) mean clustering and canonical materialization **must re-run on every ingest**, not first-seen — the riskiest part. Indoor/no-distance rides (the repro had `distance=0.0`) break a distance-based fingerprint, so the match must fall back to `(sport-class, start±, duration±)`. Match on the **coarse** sport class (`activity`/`plan_sport_type`), not the fine `discipline_id` (providers resolve the same ride to different fine D-ids). And whatever wins must not weaken the per-source `*_uidx` idempotency that already works.

## 7. Interim mitigation (no code; tell the athlete)

Until Phase 3 ships: disable provider→provider auto-forward (e.g. Wahoo→Strava in the Wahoo app), or connect only one of any overlapping pair. Delete existing duplicate rows by hand (the repro's rows 73/74 are test data).

## 8. Rule #9/#10 verification anchors (for the building session)

| Claim | File | Anchor | Check |
|---|---|---|---|
| Per-source unique indexes exist | `init_db.py` | `cardio_log_wahoo_workout_uidx` (+ strava/polar/coros/rwgps) | grep |
| Shared cardio writer + source map | `routes/garmin.py` | `def _bulk_insert_cardio` / `_SOURCE_MAP` | grep |
| Per-source idempotency guard (pattern) | `routes/wahoo.py` | `SKIP already-imported` | grep |
| Provenance pattern to reuse | (repo) | `athlete_profile_field_provenance` | grep |
| Files-list consumer | `routes/connections.py` | `_ACTIVITY_SQL` | grep |
| Athlete-state consumer | `layer3a/integration.py` / `layer4/context.py` | `cardio_log` reads | grep |

## 9. Open questions (carry from the epic — decide with Andy during ratification)

- Completeness-scoring weights — what makes one source "more robust" for a given activity?
- Dedup tolerance windows — start-time ± minutes, duration/distance ± %.
- Conflict surfacing — show the athlete when sources materially disagree, or merge silently?

## 10. Operating notes

- Slices are **separate PRs**; Slice 1 is **blocked on Andy's Trigger-#3 DDL ratification**.
- Not to be confused with the **#213 Layer-3D "input fingerprint"** (staleness `evaluated_against`) — unrelated; this is an *activity* fingerprint.
- Reconcile #196 when slices land (keep open until Slice 4 repoints consumers). The Wahoo go-live items are already reconciled on #681.
- Bookkeeping rides the work PR (CLAUDE.md operating flow) — this kickoff doc is the exception, written at Andy's explicit request.
