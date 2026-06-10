# V5 Implementation — Layer 0 Slice 1: `validate_layer0` integrity gate (+ design sign-off)

**Date:** 2026-06-10
**Branch:** `claude/exciting-mayer-enbgvg` · **PR [#510](https://github.com/ahorn885/exercise/pull/510)** (sign-off) + **PR [#513](https://github.com/ahorn885/exercise/pull/513)** (gate) · **Epic [#488](https://github.com/ahorn885/exercise/issues/488)** · spun-out **[#509](https://github.com/ahorn885/exercise/issues/509)**

## 1. What this session was

Andy opened with "I think there are some open questions before we start the xlsx→DB migration?" We resolved the 3 open decisions (A/B/C) on the Layer 0 authoring-model design, recorded the sign-off, then built **Slice 1 — the `validate_layer0` integrity gate** — end-to-end to a green CI gate + Neon apply. A `default_inclusion` deep-dive during decision C surfaced a real Layer 2A serving bug, spun out as #509.

## 2. Decisions resolved (Andy 2026-06-10) → PR #510

- **A — admin editing UI:** defer (no Flask admin surface in v1).
- **B — DB→xlsx export hedge:** build at phase 4.
- **C — validator FAIL/WARN:** **all checks FAIL**, with one **waiver bucket** (`sum_to_100`, by-design sub-100 sports) and two **fix-the-data buckets** (`vocab_alignment`, `contraindicated_conditions` — reconcile, not waive). `default_inclusion` FAIL as a closed enum (it was *already* ERROR-severity in the ETL; the spec §5.2 "WARN → revisit" label was wrong — corrected).
- Recorded by approving `Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` **in place** (DRAFT review artifact → APPROVED) + updating epic #488.

## 3. Shipped

**PR #513 — Slice 1, the integrity gate** (merged `ae8ac9c`):
- `etl/layer0/validate_layer0.py` — orchestrator + CLI. Runs all 8 validator funcs (7 logical checks; fk_checks splits in two), extracts stable violation ids, filters through the waiver registry, prints a report, exits non-zero on any unwaived violation. `db.connect` is lazy so the pure logic is unit-testable without psycopg2.
- `etl/layer0/layer0_validation_waivers.json` — 5 `sum_to_100` waivers (policy: only `sum_to_100` waivable; vocab/contraindicated fix-not-waive, enforced by review).
- `etl/tests/test_validate_layer0.py` — 12 DB-free unit tests on the evaluate/extract/waiver path.
- `.github/workflows/ci.yml` — new `layer0-gate` job: throwaway `postgres:16` + `schema.sql` + latest committed snapshot (`etl/output/layer0_etl_v*.sql`) → runs the gate. **No Neon needed** — validates the committed snapshot (the spec §5.1 "scratch schema").

**The gate's first CI run = the violation inventory** (couldn't be produced locally — container has no Postgres server, Neon egress blocked):
- Clean: `fk_checks` ×2, `discipline_canon`, `modality_group_orphan`, `contraindicated_conditions` (so its triage was a no-op), `default_inclusion`.
- `sum_to_100` — 5 by-design sub-100 sports **waived**: Canoe/Kayak Marathon (Ultra), Marathon (Mountain), Mountain Running/Skyrunning, Swimrun, Ultramarathon (Trail).
- `vocab_alignment` — 1: **18 `Fencing` exercise-mappings** orphaned by the 2026-05-30 Modern Pentathlon canon removal (the sport filter only dropped the parent sport, not the discipline-name tag).

**Fencing fixed at source** (decision C "fix the data"): `sport_canon.REMOVED_EXERCISE_DB_SPORTS = {Fencing, Laser Run, Rifle Shooting}` lockstep filter, applied to `sport_exercise_map` in `run.py` → re-emit `etl/output/layer0_etl_v1.6.7.sql` (structural diff vs prior = exactly the 18 rows). **Andy applied v1.6.7 to Neon** (bumps 0A/0B/0C → v1.6.7; full Layer-0 cache refresh).

## 4. Mid-flight reconciliation (two detours)

- **CI went silent after the data-pass push.** Root cause: main advanced (the parallel **X1b.3b** craft-aliases work merged), putting #513 into a merge-conflict (`mergeable_state: dirty`) — which **silently stops the `pull_request` CI trigger** (Vercel still deploys, so it looks live). Fix: merge `origin/main`, push → trigger restored. *(Worth remembering: a dirty PR = no Actions runs, no failure signal.)*
- **v1.6.6 add/add collision.** main also emitted its own `layer0_etl_v1.6.6.sql` (X1b.3b). Kept main's as the historical artifact (Rule #12), regenerated **v1.6.7** from the combined tree — verified it carries *both* X1b.3b craft-aliases *and* the Fencing fix. **X1b.3b data passed the strict gate with zero new violations.**

## 5. Stop-and-ask status

None pending. **#509** (Layer 2A inclusion-precedence) is the spun-out design item — triggers #3 (Layer 0→2A contract) + #4 (HITL); sequenced with X3/X4; **out of this epic's scope**. The unification target is the established precedence **race > athlete > curator default** (Modality_Group_Spec_v1 §5.1), confirmed by Andy this session.

## 6. Owed / next move

1. **`etl/migrations/layer0/` convention + first proof migration** — the DB-native authoring loop (the next real slice of #488). **Open item E** lands here: confirm nothing downstream assumes Layer 0 versions only advance via a *full* ETL run (`etl_version_set` pinning / partial-update invalidation; trigger #3 check). *Not done this session.*
2. **Phase 4** — freeze `etl/layer0/extractors/`, `run.py`, `emit_sql.py`, and the v14/v19 workbooks once 2–3 migrations have gone through cleanly.
3. **#509** — Layer 2A inclusion unification, sequenced with X3/X4.
4. **DB→xlsx export** (decision B, phase 4).

**Drift flagged:** main's `CURRENT_STATE.md` "Last shipped session" pointer was still the 06-09 xlsx-retirement handoff when X1b.3b merged — i.e. X1b.3b shipped to `main` **without** updating the pointer or chaining a handoff entry. This handoff re-points it to 06-10; the X1b.3b session has no CURRENT_STATE entry (run `git log` on `etl/layer0/extractors/sports_framework.py` for its commit if its detail is needed).

### 6.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. this handoff · 5. `./scripts/verify-handoff.sh`. Then read epic #488 + `Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` before touching Layer 0 authoring.

## 7. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Gate orchestrator + CLI | `etl/layer0/validate_layer0.py` | `def evaluate(` + `CHECKS` tuple (8 entries) |
| Waiver registry (5) | `etl/layer0/layer0_validation_waivers.json` | 5× `"check": "sum_to_100"`; `Swimrun` present |
| Gate unit tests (12) | `etl/tests/test_validate_layer0.py` | `test_sum_to_100_waived_passes` |
| CI gate job | `.github/workflows/ci.yml` | `layer0-gate:` + `python -m etl.layer0.validate_layer0` |
| Fencing lockstep filter | `etl/layer0/sport_canon.py` | `REMOVED_EXERCISE_DB_SPORTS` |
| Filter applied to sxm | `etl/layer0/run.py` | `is_removed_exercise_db_sport` (near `sport_exercise_map` insert) |
| Clean snapshot | `etl/output/layer0_etl_v1.6.7.sql` | `grep -c "'Fencing'"` → 0; `craft_discipline_aliases` INSERT present |
| Decisions recorded | `aidstation-sources/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` | `**Status:** APPROVED` + §5.2 disposition table |
| Slice 1 marked done | GitHub | epic #488 latest comment; #509 filed |

## 8. Summary

Slice 1 — the `validate_layer0` integrity gate — is **live and CI-enforced over `layer0.*`** (the prerequisite the rest of #488 was waiting on; previously the validators only ran as a side effect of re-running the ETL). Design decisions A/B/C signed off (#510). The gate (#513) surfaced and resolved the genesis inventory: 5 by-design sub-100 sports waived; the orphaned `Fencing` mappings fixed at source (v1.6.7, Neon-applied). Two detours — a dirty-merge CI stall and a v1.6.6 collision with the parallel X1b.3b advance — both reconciled. Next: the `etl/migrations/layer0/` convention + open item E.
