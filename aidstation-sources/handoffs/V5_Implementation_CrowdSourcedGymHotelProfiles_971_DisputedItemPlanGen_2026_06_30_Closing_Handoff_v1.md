# Crowd-Sourced Gym/Hotel Profiles (#971) — Layer-2C: Disputed Item ⇒ Not-Available for Plan-Gen — Closing Handoff

**Session:** The LAST remaining #971 piece — the cross-layer plan-gen follow-up the Slice-3 design left as the committed next step. Slices 1 (name+geo dedup) + 2 (photos) + 3 (admin review) all shipped+merged before this.
**Date:** 2026-06-30
**Predecessor handoff:** `handoffs/V5_Implementation_CrowdSourcedGymHotelProfiles_971_Slice2_Photos_2026_06_29_Closing_Handoff_v1.md` (§6.1 = this slice's recipe).
**Branch:** `claude/crowd-sourced-gym-hotel-profiles-ip8w91`
**Status:** 2 substantive code files + 1 spec + 1 new design + 3 test files touched. Full suite green (**3954 passed, 30 skipped**). **PR opens on Andy's go** (push + bookkeep + wait — per the ops operating flow).

---

## 1. Session-start verification (Rule #9)

| Claim | Anchor | Result |
|---|---|---|
| `verify-handoff.sh` clean, 0 ❌ | `aidstation-sources/scripts/verify-handoff.sh` | ✅ |
| Slices 1+2+3 shipped+merged | git log: merge commit `98f1da9` (PR #1033, Slice 2); Slice-3 + Slice-1 prior | ✅ |
| Slice-2 §8 anchors landed (the photo feature) | `gym_profile_photos` DDL, photo helpers/routes, admin queue — all present | ✅ |
| Disputed-tag substrate exists | `gym_profiles.disputed_items` populated by Slice 3 `_record_profile_edit`; `{by,adds,removes,at}` shape | ✅ |
| Working tree clean | git status | ✅ |

**Reconciliation note:** clean. This session is the committed next step (Slice-2 handoff §6.1), the only remaining #971 work.

---

## 2. Session narrative

**The decision was already made; the *how* was owed.** D-60 §5's treatment — "a disputed item is not-available for plan generation" — was approved by Andy 2026-06-29. The Slice-3 handoff §6.1 flagged this as a **cross-layer change (stop-and-ask trigger #3)**: scope it, surface options/tradeoffs, get explicit confirmation before building. I read the seams first, then surfaced two genuine design forks via `AskUserQuestion` (CLAUDE.md "think before coding").

**The two forks (both ratified by Andy 2026-06-30):**

1. **Subtraction seam → PLAN-GEN ONLY.** `locations.locale_effective_tags` is the single authoritative chokepoint, but it *also* feeds the locale UI + references view + the override-save diff. Subtracting only on the plan-gen paths (vs. everywhere) means the athlete's own equipment view still shows the real shared set — no confusing "my gym lost a treadmill" from a peer's flag — while the plan stops prescribing the disputed tag. Matches the D-60 wording precisely.
2. **Invalidation → LAZY / NEXT-REGEN.** The 2C cache is content-addressed (the equipment pool is hashed into the cache key), so subtracting the disputed tag changes the hash → the tag drops out at each inheritor's *next* natural plan create/refresh. No proactive cross-inheritor eviction. A dispute is a soft, unreviewed one-peer signal; churning every inheritor's live plan on one flag is the wrong default.

**Defaults ratified from the §6.1 direction (stated, not re-asked):** subtract for **all inheritors**; **disputed *adds* need no handling** (not in the shared set until an admin approves, so they never drive plan-gen — only `removes` matter).

**The proposer was already covered.** When a peer flags a correction, Slice 3 already writes their personal `locale_equipment_overrides` remove + evicts *their* 2C cache. So their plan already excludes the tag — this slice is about applying it to the **other** inheritors.

**Spec-first (the input-contract change).** Wrote `designs/CrowdSourcedProfiles_DisputedItemPlanGen_971_Design_v1.md` before code (it touches Layer 2C's `locale_equipment_pool` input), then a cross-ref into `Layer2C_Spec.md` §3/§12. 2C's own algorithm is unchanged — only the upstream pool construction in `locations.py`.

---

## 3. File-by-file edits

### 3.1 `locations.py` (modified) — the whole behavior change lives here
- **New `disputed_equipment_tags(db, gym_profile_id) -> set[str]`** — SELECT `disputed_items`, parse tolerantly (NULL/empty/malformed → `set()`, mirrors the inline `equipment` parse), return the **union of every open proposal's `removes`** (string entries only). Lives here (a pure domain module, no `routes/locales` import) to avoid a circular dependency.
- **`locale_effective_tags` gained `*, exclude_disputed: bool = False`.** When `True` *and* the locale links a `gym_profile_id`, subtract `disputed_equipment_tags(...)` from `shared` **before** the override math: `((shared − disputed) ∪ adds) − removes`. Subtracting from `shared` only (not `adds`) means **a personal override re-add beats a peer's provisional dispute** (personal affirmation is authoritative for that athlete). Rule-#15 log fires when the subtraction actually removes something (user_id + locale + the disputed∩shared set). The UI path adds **zero queries** (the extra SELECT is behind the `exclude_disputed` + `gym_profile_id` guards).
- **`cluster_effective_tags` + `cluster_equipment_by_locale`** now call `locale_effective_tags(..., exclude_disputed=True)` (both are plan-gen helpers).

### 3.2 `layer4/orchestrator.py` (modified) — pass the flag from the 3 plan-gen callsites
- `:1218` — the per-locale 2C payload pool (`q_layer2c_equipment_mapper_payload(locale_equipment_pool=...)`).
- `:2313` — the `locale_equipment` map folded into the plan-gen **cache-key bundle** (so the hash reflects the disputed-adjusted pool → the lazy-invalidation mechanism).
- `_q_locale_equipment_pool` (`:2345`, single-session path).

### 3.3 `aidstation-sources/specs/Layer2C_Spec.md` (modified)
- §3 Parameters: `locale_equipment_pool` note documents the `exclude_disputed=True` plan-gen construction + the design cross-ref.
- §12 Open items: new row **2C-6 — Resolved 2026-06-30** (plan-gen-only + lazy).

### 3.4 `aidstation-sources/designs/CrowdSourcedProfiles_DisputedItemPlanGen_971_Design_v1.md` (new)
Build-ready design: purpose, the seam table (which callers are disputed-aware vs. UI), algorithm (`((shared − disputed) ∪ adds) − removes`), the lazy-invalidation rationale, edge cases, test scenarios, gut check.

### 3.5 Tests (3 files touched)
- **`tests/test_locations.py` (+8):** `_FakeDB` gained a `disputed` map + a `disputed_items FROM gym_profiles` dispatch branch (checked before the equipment branch — same substring). New cases: `disputed_equipment_tags` union/tolerance; plan-gen excludes a disputed tag while the UI default keeps it; personal-add beats a peer dispute; withdraw restores; no-linked-profile skips the query; `cluster_equipment_by_locale` excludes disputed.
- **`tests/test_gate_input_fingerprint.py`:** the `locale_effective_tags` monkeypatch lambda gained `**kw` (now called with `exclude_disputed=`).
- **`tests/test_layer4_location_baselines.py`:** `_FakeDB` gained the same `disputed_items` branch (`cluster_equipment_by_locale` now issues that query).
- **`tests/test_layer4_orchestrator.py`:** the `locale_effective_tags` patch lambda gained `**kw`.

---

## 4. Verification

- **Full `tests/` → 3954 passed, 30 skipped** (was 3846 at Slice 2; +8 disputed cases + the unchanged remainder). Only the 3 pre-existing #217 Layer3B warnings.
- The change is exercised both directions: `exclude_disputed=True` subtracts; the default (UI/save/legacy callers) is byte-identical to before.

---

## 5. Manual §5.0 verification (live, ≥2 accounts; recorded in `CARRY_FORWARD.md`)

B inherits A's shared profile and **ticks "report wrong"** removing a tag (e.g. Treadmill) → that tag is absent from the equipment pool when a **third** inheritor C generates/refreshes a plan (confirm via `/admin/logs` `locale_effective_tags: … disputed-excluded`), while A's and C's **locale equipment view still shows the tag** (plan-gen-only). Admin **reject** or B **withdraw** restores it at the next plan op (lazy — not immediate on an already-generated plan).

---

## 6. Next session pointers

### 6.1 #971 is COMPLETE
All four pieces shipped: Slice 1 (name+geo dedup) + Slice 2 (photos) + Slice 3 (admin review) + this Layer-2C disputed-item plan-gen treatment. **Close issue #971 on the merge.** Nothing #971 is owed beyond the §5.0 live walkthrough above.

### 6.2 Where to look next (not chosen this session)
Per the 4-tier next-step order, the standing live threads from the predecessor handoffs: the **#884** unified gear/craft slice-6c arc (onboarding parity + legacy retirement + the deferred per-segment 2C re-resolve) and the **#964** conditions-advisory Slice 2 (#964 consumer over the #289 producer). See `CURRENT_STATE.md` "Last shipped session" + the respective handoffs. Pick per the tier order with Andy.

### 6.3 Operating notes for next session
1. **Read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.
2. **No Neon/layer0 apply owed** — read-time subtraction, no schema change; the pool is recomputed on read, never pinned to `etl_version_set`.
3. **Postgres-only repo;** the `_FakeDB` substrates in `tests/test_locations.py` + `tests/test_layer4_location_baselines.py` unit-test the resolution logic without a live DB. Both now serve the `disputed_items` query — extend that branch if you add disputed-path coverage elsewhere.
4. **Possible follow-ups (out of scope, not owed):** (a) an athlete-facing "under review" UI hint on a disputed tag's locale chip; (b) an admin signal of how many inheritors an open dispute currently affects; (c) the rejected fork-2 option (proactive cross-inheritor eviction) is the additive upgrade path if lazy invalidation ever bites. None are blockers.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | **Plan-gen-only subtraction** (not in the locale UI / references view) | **Andy (2026-06-30, AskUserQuestion)** | Matches D-60 wording; the athlete's own equipment view stays the real shared set — no confusing "my gym lost X" from a peer's flag; only the plan stops prescribing it. |
| 2 | **Lazy / next-regen invalidation** (no proactive eviction) | **Andy (2026-06-30, AskUserQuestion)** | The content-addressed 2C cache key changes when the pool changes, so the disputed tag drops out at the next plan op. A provisional one-peer flag shouldn't churn every inheritor's live plan. |
| 3 | Subtract disputed from `shared` **only**, not `adds` → a personal override re-add beats a peer's dispute | Claude (stated in design) | A personal override is authoritative for that athlete; a peer's provisional dispute shouldn't override their explicit affirmation. |
| 4 | Disputed **adds** need no handling | Claude (from §6.1 direction) | A proposal's `adds` aren't in the shared set until an admin approves them, so they never drive plan-gen. |
| 5 | Seam in `locations.py` via a default-False kwarg (not a one-line edit at the chokepoint) | Claude (surgical) | Keeps every UI/save/legacy caller byte-identical; the disputed read is added only on the 5 plan-gen callsites. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `disputed_equipment_tags` + `exclude_disputed` kwarg in `locations.py` | ✅ `locations.py` |
| `cluster_effective_tags` + `cluster_equipment_by_locale` pass `exclude_disputed=True` | ✅ `locations.py` |
| 3 orchestrator callsites pass `exclude_disputed=True` (`:1218`/`:2313`/`_q_locale_equipment_pool`) | ✅ `layer4/orchestrator.py` |
| Layer2C_Spec §3 note + §12 Open Item 2C-6 (Resolved) | ✅ `specs/Layer2C_Spec.md` |
| Design doc present | ✅ `designs/CrowdSourcedProfiles_DisputedItemPlanGen_971_Design_v1.md` |
| `test_locations.py` disputed cases + `_FakeDB` branch; mock-signature fixes | ✅ 3 test files |
| Full suite 3954 passed / 30 skipped | ✅ pytest |
| Bookkeeping (`CURRENT_STATE.md` + `CARRY_FORWARD.md` + this handoff) committed with the slice | ✅ git |

---

## 9. Files shipped this session

**Substantive (2 code + 1 spec + 1 design; + 3 test):**
1. `locations.py`
2. `layer4/orchestrator.py`
3. `aidstation-sources/specs/Layer2C_Spec.md`
4. `aidstation-sources/designs/CrowdSourcedProfiles_DisputedItemPlanGen_971_Design_v1.md` (new)
5. `tests/test_locations.py`
6. `tests/test_gate_input_fingerprint.py`
7. `tests/test_layer4_location_baselines.py`
8. `tests/test_layer4_orchestrator.py`

Under the 5-substantive-file ceiling (the 3 non-`test_locations` test edits are 1-line mock-signature / substrate updates forced by the new kwarg).

**Bookkeeping (3 files, outside the count):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

**End of handoff.**
