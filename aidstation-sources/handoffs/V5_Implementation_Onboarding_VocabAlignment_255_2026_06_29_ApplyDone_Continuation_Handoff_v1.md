# V5 — #255 vocab alignment: SHIPPED + APPLIED, and the continuation toward #253

**Status:** #255 fully landed end-to-end. This handoff records the prod apply and **sets up the next step** so the following session continues without re-deriving scope.

**Supersedes (in sequence):** `handoffs/V5_Implementation_Onboarding_VocabAlignment_255_2026_06_29_Closing_Handoff_v1.md` (the closing handoff that rode PR #1013). Read that first for the full #255 build detail; this one is the apply-confirmation + continuation pointer.

---

## 1. #255 is done — shipped and applied

- **PR [#1013](https://github.com/ahorn885/exercise/pull/1013) MERGED** (`f209f58`). It landed on the **`v1.10.0`** Layer 0 baseline after a clean conflict-resolve — the #884-4.3 redump (`v1.9.0`→`v1.10.0`, `0023`–`0030` archived) plus #215/#964/#971 merged to `main` while #1013 was open; only `CURRENT_STATE.md` truly conflicted. Re-validated against `v1.10.0`: `validate_layer0` PASS, full suite 3781 passed / 30 skipped.
- **`layer0-apply` run `28385901630` APPLIED both migrations to prod Neon** (Andy approved the production gate):
  - `0031` (supplement contraindication retag): `UPDATE 5` rows (magnesium/carb_powder/iron → `gi`; electrolyte_mix/sodium_bicarbonate → `endocrine_metabolic`; `gi_immune`→`gi` only, not autoimmune) + ledger insert.
  - `0032` (body_parts hygiene): `UPDATE 2` (singular Bicep/Tricep superseded) + Collarbone `INSERT 0 1` + ledger insert.
- Net: the athlete `system_category` enum, the Layer 2E supplement-screening vocab, and the injury body-part picker are now all on the canonical vocab. **Nothing owed on #255.**

## 2. The next step — continue epic #246 toward #253 (supplement de-stub)

**We will continue with #253.** Grounding finding from this session (verify first, per Rule #9):

- **#253's literal deliverable already exists.** The issue says "add an `athlete_supplement_records` table + a Layer 1 builder." That capture surface **already shipped** under the 2E-6 work, just under a different name:
  - Table: `athlete_supplements` (`init_db.py:1741`, with `frequency`/`timing` columns).
  - Repo: `athlete_supplements_repo.py` — `load_supplement_vocab`, `vocab_index`, `list/add/delete_athlete_supplement`.
  - Layer 1 builder: `layer1/builder.py` `_load_supplements` → `AthleteSupplementRecord` ("consumed by Layer 2E §5.5").
  - UI: profile capture (`routes/profile.py` "2E-6 structured supplement capture").
- So the issue text is **stale**; the real remaining work it points at ("unblocks the Layer 2E supplement de-stub") is the **Layer 2E §5.5 supplement de-stub**: `layer2e/builder.py` `_stub_supplement_integration` (the "vertical_slice stub", grep `stub_phase` / `vertical_slice_2_5`). It is now unblocked because #255 put the supplement-vocab `contraindications` on the same canonical slugs the athlete `system_category` uses, which is exactly what `_contraindication_hits` matches.

**First action next session:** confirm the above against the live tree (Rule #9 grep), then **check the tracker** — there is very likely a dedicated Layer 2E supplement-de-stub issue distinct from #253 (the #210/#215/#220/#221 Layer 2E de-stub arc is active; the Plan Management spec #215 just landed). Decide with Andy whether to (a) close/relabel #253 as already-built capture and open/locate the de-stub issue, or (b) treat the de-stub as #253's remaining scope.

**Likely stop-and-ask:** the §5.5 de-stub replaces a stub with real screening logic against the captured protocol — if it touches a Layer 2E prompt body or changes the 2E payload contract, that's Trigger #1/#3. Surface the de-stub design (what it consumes, what flags/payload it emits, caching) before implementing.

## 3. §6.3 — read order for next session

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — the #255 entry (now marked SHIPPED + APPLIED) + the #246/#253 continuation note
3. `CARRY_FORWARD.md`
4. This handoff
5. (no `scripts/verify-handoff.sh` present in-repo — do the Rule #9 spot-check by grep: `_stub_supplement_integration` in `layer2e/builder.py`, `_load_supplements` in `layer1/builder.py`, `athlete_supplements` in `init_db.py`)

## 4. Verification anchors (Rule #10)

| Claim | Anchor | Check |
|---|---|---|
| #255 enum canonical | `endocrine_metabolic` in `athlete.py` `KNOWN_SYSTEM_CATEGORIES` | grep |
| #255 body parts | `BODY_PART_GROUPS` in `routes/injuries.py` | grep |
| 0031/0032 applied | run `28385901630` log: `UPDATE 5` / Collarbone `INSERT 0 1` | Actions log |
| capture already built | `athlete_supplements_repo.py` + `_load_supplements` in `layer1/builder.py` | grep |
| de-stub target | `_stub_supplement_integration` in `layer2e/builder.py` | grep |
