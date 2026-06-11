# Layer 0 Authoring Model — DB as Source of Truth — Design Spec v1

**Status:** APPROVED — Andy sign-off 2026-06-10. Decisions A/B/C resolved (see §5.2 + §8). Slice 1 (the `validate_layer0` validator port) is cleared to build; nothing else ships before it. *(Approved in place from the v1 DRAFT review artifact — the lifecycle close of that draft, not a content revision; git holds the draft state.)*
**Date:** 2026-06-09
**Scope:** Retire the legacy xlsx "foundational documents" as the authoring source of truth for Layer 0 reference data; make the `layer0.*` Postgres tables authoritative. Serving path is already DB-only — this is purely an *authoring/curation* change plus porting the validation gate off the ETL.

---

## 1. Purpose

Today, Layer 0 platform reference data (sport rule sets, exercise library, canonical vocabularies) is **authored in spreadsheets** and projected into Postgres by a one-time ETL:

```
edit Sports_Framework_v14.xlsx / AR_Exercise_Database_v19.xlsx / Vocabulary_Audit_v2.md
  → python -m etl.layer0.run --version-tag X     (extract + canon-transform + validate)
  → supersede-before-insert into layer0.* (etl_version, etl_run_at, superseded_at)
  → emit_sql.py → etl/output/layer0_etl_vX.sql   → Andy pastes into Neon SQL editor
```

The spreadsheet is the canonical *input*; the DB is a regenerated *projection*. "Stop relying on the xlsx" = invert that: the DB row becomes the artifact we edit, edits arrive as reviewed SQL migrations, and the workbook is retired (or kept only as a derived export).

## 2. Current state — what "relying on the xlsx" actually means

**The xlsx is NOT a runtime dependency.** Verified this session:

- Zero `read_excel` / `openpyxl` / `load_workbook` / `.xlsx` reads in `app.py`, `coaching.py`, `routes/`, or any `layer1`–`layer4` builder. The single `.xlsx` token in `init_db.py:1633` is a comment.
- Every serving path reads `layer0.*` Postgres tables — 77 `layer0.` query references across 11 modules — filtering `WHERE superseded_at IS NULL` for current data.
- The app would run identically if every `.xlsx` were deleted from disk (after the ETL has run once).

So in the **serving** sense the DB is already the source of truth. What we still rely on the xlsx for is three things the ETL does, in order of how hard they are to give up:

| ETL job | Where it lives | Replaceable? |
|---|---|---|
| **(1) Translation** — regex/string parsers turning messy human columns into canonical JSONB/FK shape | `etl/layer0/extractors/*`, `vocabulary_transforms.py`, `discipline_canon.py`, `sport_canon.py` | Yes — once we author in the already-canonical shape, this code is deleted, not ported. |
| **(2) Validation** — `sum_to_100`, `vocab_alignment`, `fk_checks`, `discipline_canon_check`, `modality_group_orphan`, `contraindicated_conditions`, `default_inclusion` | `etl/layer0/validation/*` | **Must be ported.** This is the only systematic integrity check on Layer 0 today. |
| **(3) Versioning** — supersede-before-insert, full history in-row | `etl/layer0/db.py` (`insert_versioned`) | Already DB-native; keep the pattern, drive it from migrations instead of an ETL run. |

**Job (2) is the load-bearing risk.** The validators run *because* we re-run the ETL. Go DB-authoritative without porting them and we lose the integrity backstop silently. Porting the validation gate is the real project; the data move is trivial by comparison.

## 3. Proposed decisions (pending Andy)

1. **DB row is canonical; xlsx is retired.** After a final genesis snapshot, no further authoring in the workbooks. New reference-data changes are reviewed SQL migrations in git.
2. **Edits are versioned SQL migrations, not spreadsheet diffs.** Reuse the existing supersede-before-insert discipline (one `etl_version` per source family, `superseded_at` flip). Source artifact = a reviewed `.sql` in the repo, applied via Neon SQL editor (container can't reach Neon — unchanged constraint).
3. **Port the validators to run against the DB**, as a standalone `validate_layer0` pass wired into CI. Most already query the DB, not the workbook — see §5.2.
4. **No admin editing UI in v1.** Andy is the sole curator and recent Layer 0 work is surgical (X1a bridge bands, X1b modality groups, D-007 cleanup). SQL migrations fit that shape. Revisit a Flask admin surface only if a wholesale re-curation lands (the Flask app *can* reach Neon at runtime, so it's the natural home if we ever need one). — **Decision A — RESOLVED 2026-06-10: defer (no admin UI in v1).**
5. **Keep a DB→xlsx export as the bulk-review hedge.** A read-only export script preserves the one thing the spreadsheet is genuinely better at (seeing all 245 exercises / 38 sports at once) while inverting the dependency. — **Decision B — RESOLVED 2026-06-10: build at phase 4.**

## 4. Why this shape (alternatives considered)

- **Option A — keep ETL, just re-label xlsx as "reference doc."** Cheapest (operationally already true), but leaves the authoring loop and the duplicate-workbook rot in place; doesn't actually retire anything. Rejected as the end state — it's where we are today.
- **Option B — convert xlsx → version-controlled SQL seeds, ETL reads SQL.** Git-friendly/diffable, but keeps a redundant intermediate format and most of the extractor code. Half-measure.
- **Option C (recommended) — DB is authoritative; edits are SQL migrations; validators port to a DB-side gate; extractors + xlsx retire.** Deletes the most code (the translation layer), keeps the versioning we already have, and forces the validation gate to become first-class. The only thing it gives up — bulk visual review — is recovered by the §3.5 export hedge.

## 5. Target authoring model

### 5.1 Edit flow (replaces the spreadsheet loop)

```
write etl/migrations/layer0/NNNN_<change>.sql   (supersede prior etl_version, insert new rows)
  → run validate_layer0 locally + in CI (reads the would-be-applied state or a scratch schema)
  → review the .sql diff in the PR
  → Andy applies in Neon SQL editor
  → app picks up new rows automatically (WHERE superseded_at IS NULL); no restart, no app deploy
```

### 5.2 The validation gate (`validate_layer0`)

A standalone module/CLI that runs the existing checks against `layer0.*` and exits non-zero on hard failures. Inventory + proposed disposition:

| Validator | Reads DB today? | Proposed home | Disposition (decision C — RESOLVED 2026-06-10) |
|---|---|---|---|
| `fk_checks` (substitution + training-gap FKs) | yes | `validate_layer0` + consider real FK constraints | **FAIL** (a dangling FK is never intended) |
| `discipline_canon_check` | yes | `validate_layer0` | **FAIL** |
| `modality_group_orphan` | yes | `validate_layer0` (already ERROR-severity) | **FAIL** |
| `sum_to_100` | yes | `validate_layer0` | **FAIL + waiver registry** — the intentionally sub-100 sports get explicit, reviewed, dated waivers; gate fails on any *unwaived* violation |
| `vocab_alignment` | yes | `validate_layer0` | **FAIL — fix the data** (reconcile the documented by-design mismatches; no waiver) |
| `contraindicated_conditions` | yes | `validate_layer0` | **FAIL — triage the data** (typos fixed; a genuinely-new condition category is a no-padding / trigger-#2 call before it passes) |
| `default_inclusion` | yes | `validate_layer0` | **FAIL** (closed enum `included`/`excluded`/`prompt_required`; no legitimate exception, so no waiver) |

**Correction:** the `default_inclusion` validator is **already ERROR-severity in the ETL today** (`etl/layer0/validation/default_inclusion.py` docstring: "Mismatch → ERROR") — the prior "WARN → revisit" lumping understated its current state; FAIL in `validate_layer0` preserves existing behavior. Separately, the *serving* consumption of `default_inclusion` is a known bug (Layer 2A ignores the column and re-derives from `notes_conditions`, losing authored `excluded`/`included` intent) — tracked as **#509**, out of scope here; the FAIL guards the column's integrity regardless of which path serving reads.

**Decision C — RESOLVED 2026-06-10:** all validators graduate to FAIL, with exactly one waiver bucket (`sum_to_100`) and two clean-the-data-first buckets (`vocab_alignment`, `contraindicated_conditions`). These are mostly mechanical to lift because they already take a DB connection, not the workbook.

### 5.3 Versioning

Keep `(etl_version, etl_run_at, superseded_at)` and the supersede-before-insert ordering (DELETE same-version → UPDATE supersede prior → INSERT active — the ordering fix from X1a / PR #475 stays). `etl_version_set` is still a `{0A,0B,0C}` cache-key component, but **slice 3b (2026-06-11) decoupled it from serving**: the Layer 2 builders now read the active set (`WHERE superseded_at IS NULL`) and no longer match on `etl_version`, so a migration serves the moment it commits. `_q_current_etl_version_set` now digests each family's active version **per table** (keyed on `_LAYER0_TABLE_FAMILY`), so a serving-relevant edit can bump just the changed table — the digest shifts and invalidates the plan-gen caches with no whole-family re-stamp. (This superseded the earlier per-family exact-match, which had also masked the Open item E broadcast bug, §8.) One-time cost: the cache-key value shape changed from a single version string to a per-table digest, so the first deploy invalidates all plan-gen caches once.

## 6. Phased plan

1. **Genesis snapshot.** One final clean ETL run of v14/v19/Vocab-v2; the latest committed `etl/output/layer0_etl_v1.6.x.sql` is the reproducible genesis artifact. Declare the DB canonical from here. *(Mostly already done — the v1.6.x line is the current emitted snapshot.)*
2. **Port the validators** → `validate_layer0` + CI wire. **This is slice 1 and the first thing to build.** No authoring change ships before the gate exists.
3. **Establish `etl/migrations/layer0/`** + the migration convention (§5.1). First real DB-native edit (e.g. the #476 D-007 cleanup or #477 discipline-ID split) becomes the proof migration instead of a v15 workbook.
4. **Retire the extractors + xlsx.** Once 2–3 edits have gone through migrations cleanly, freeze `etl/layer0/extractors/`, `run.py`, `emit_sql.py`, and the two remaining workbooks (`Sports_Framework_v14.xlsx`, `AR_Exercise_Database_v19.xlsx`) into an archive (the way `Project_Backlog_vN.md` was frozen). The old-version test pins are already resolved (§7.2 — tests now run against v14, the live source).
5. **(Optional) DB→xlsx export** (decision B) and/or **admin UI** (decision A).

## 7. What gets deleted / retired

### 7.1 Stale xlsx removed in this PR (genuinely inert — no code/test reference)

- `etl/sources/Sports_Framework_v6.xlsx`
- `etl/sources/Sports_Framework_v12.xlsx` (only a stale header comment in `emit_sql.py` pointed at it — `emit_sql.py` now derives the source name dynamically from `run.py`'s `SPORTS_XLSX`, per the fix that landed on `main`)
- `etl/sources/Sports_Framework_v13.xlsx` (superseded by v14 on `main` while this branch was in flight — pruned on merge along with the rest)
- `etl/sources/AR_Exercise_Database_v17.xlsx` (the `aidstation-sources/etl/*` scripts that name v17 look for it next to themselves, not here)
- `aidstation-sources/data/AR_Exercise_Database_v19.xlsx` (exact dup of the authoritative `etl/sources/` copy — md5 match)
- `aidstation-sources/data/Sports_Framework_v10.xlsx`
- `aidstation-sources/data/Sports_Framework_v11.xlsx` (write-target of the migrate script, not read by anything)

All remain recoverable from git history; this only de-clutters the working tree and kills the "which workbook is real?" ambiguity.

### 7.2 Older versions retired in this PR (the deliberate pass — were pinned by live code)

- `etl/sources/Sports_Framework_v11.xlsx` — was read by `etl/tests/test_discipline_canon.py` + `test_v11_parsers.py`. Both repointed to **v14** (the live production source — `run.py` runs v14 through these exact extractors, so this modernizes the drift detector rather than weakening it; `test_discipline_canon.py` took `main`'s v14 repoint at 24 disciplines). The pinned parser counts (89 substitutes, 3 training gaps, 1 cross-sport property) held against v14, confirming those sheets are stable across v11→v14. `test_v11_parsers.py` renamed `test_sports_framework_parsers.py` (version-agnostic; fixture `v14_wb`). Three stale `etl/layer0` docstrings that named v11 as "the source" de-dangled to "the Sports Framework workbook".
- `etl/sources/Sports_Framework_v10.xlsx` + `etl/sources/migrate_discipline_ids_R6.py` — the already-executed one-off R6 renumber (produced v11 from v10). Both deleted; recoverable from git history.

CI is unaffected — the GitHub Actions Python job runs `pytest tests/` only, not `etl/tests/`; the repoint keeps the local ETL suite green regardless.

### 7.3 Current authoritative sources (untouched)

- `etl/sources/Sports_Framework_v14.xlsx`, `etl/sources/AR_Exercise_Database_v19.xlsx`, `etl/sources/Vocabulary_Audit_v2.md` — these stay until phase 4 retirement, after the migration path is proven. (`etl/sources/` now holds exactly these two workbooks + the vocab markdown.)

## 8. Risks / open items / gut check

- ~~**Open decision A** — admin UI now or defer~~ ✅ **RESOLVED 2026-06-10: defer** (no admin UI in v1).
- ~~**Open decision B** — DB→xlsx export hedge now or defer~~ ✅ **RESOLVED 2026-06-10: build at phase 4.**
- ~~**Open decision C** — which validators graduate WARN→FAIL~~ ✅ **RESOLVED 2026-06-10: all FAIL**, with one waiver bucket (`sum_to_100`) and two fix-the-data buckets (`vocab_alignment`, `contraindicated_conditions`). See §5.2.
- ~~**Open item D** — the v11 test pins~~ ✅ Resolved in #487 (§7.2): tests repointed to v14, v10–v13 deleted.
- ~~**Open item E** — confirm no downstream assumes Layer 0 versions only advance via a full ETL run~~ ✅ **RESOLVED 2026-06-10: it did — and the assumption was masking a live serving bug.** `_q_current_etl_version_set` (`layer4/orchestrator.py`) read only `layer0.sports` and broadcast its `0A-`prefixed version to the `0B`/`0C` keys (a self-described "v1 approximation … promote to per-sub-arc when independent versioning ships"). Since prod stores **family-prefixed** versions (`0A-v1.6.7` / `0B-v1.6.7` / `0C-v1.6.7`, confirmed by query) and Layer 2B/2C exact-match `etl_version`, terrain (2B) and the exercise pool (2C) were resolving **zero rows** — degraded silently because both fail soft to empty. **Fix (Trigger #3, Andy sign-off 2026-06-10):** read each family's own highest active version from a representative table (`sports`/0A, `exercises`/0B, `terrain_types`/0C). This both repairs the live 2B/2C bug and makes a single-family migration *observable* to cache invalidation + the version the builders query — the prerequisite for the `etl/migrations/layer0/` model. Regression guard: `tests/test_layer4_orchestrator.py::TestQCurrentEtlVersionSet`. Live verification (cold plan shows non-empty terrain + real exercise pool) is owed-Andy's-hands post-deploy.
- **New (spun out) — #509:** Layer 2A ignores the `default_inclusion` column and re-derives inclusion from `notes_conditions`, losing the curator's authored `excluded`/`included` intent (4/17 AR rows diverge in the genesis snapshot). Fix = unify inclusion onto the weighting precedence (`race > athlete > curator default`, per `Modality_Group_Spec_v1` §5.1) + wire the column + reconcile the stale `Layer2A_Spec` §5.3 ("not a column" — false since schema v10). Triggers #3/#4; sequenced with X3/X4; **out of this epic's authoring-migration scope.**

**Gut check:**
- *Best argument against the whole thing:* the spreadsheet's real value is bulk human review. If a wholesale exercise-DB re-curation is on the roadmap, SQL migrations are the wrong tool and you'll miss the workbook — the §3.5 export is the only thing that makes full retirement safe. If we won't build the export, consider keeping the xlsx as the bulk-edit tool for 0B (exercises) only and migrating 0A/0C.
- *Biggest risk:* shipping any authoring change before §6.2 (the validator port). Don't reorder — the gate is the prerequisite, not the polish.
- *What I might be missing:* whether the canon transforms are truly idempotent against already-canonical input. If any extractor is *only* correct on raw-spreadsheet shape, hand-authored canonical rows could diverge from ETL-authored ones. Worth a one-time audit before phase 3.

## 9. Tracking

Epic filed: **[#488](https://github.com/ahorn885/exercise/issues/488)** — "Retire legacy xlsx foundational docs → DB as source of truth" (`layer:0`, `area:etl`, `v2`). The task checklist lives there. Status as of 2026-06-10 (spec **APPROVED**; decisions A/B/C resolved):

- [x] Prune stale/superseded workbooks; retire v10/v11.
- [x] Add `etl/tests/` to the CI Python job (see §10).
- [ ] Slice 1 — `validate_layer0` port + CI wire (the integrity gate; nothing ships before it). Includes: `sum_to_100` waiver registry · fix `vocab_alignment` data · triage `contraindicated_conditions` data · clear open item E.
- [ ] `etl/migrations/layer0/` convention + first proof migration.
- [ ] Phase 4 — freeze extractors + remaining workbooks (v14/v19).
- [ ] DB→xlsx export (decision B — at phase 4).
- [ ] **#509** (spun out) — Layer 2A inclusion-precedence unification + wire `default_inclusion` column. Out of scope here; sequenced with X3/X4.

## 10. CI coverage note (shipped in #487)

The Layer 0 ETL parser + discipline-canon tests (`etl/tests/`) were **not CI-gated** — the GitHub Actions Python job ran `pytest tests/` only. A future change breaking the ETL extractors would have passed CI green. Folded `etl/tests/` into the same job (`pytest tests/ etl/tests/`); `psycopg2` is already installed via `requirements.txt` and the ETL tests read the source workbooks directly (no live DB needed). This is a prerequisite-grade safety net for the rest of the migration — the extractor/canon code is exactly what the later phases will touch and retire.
