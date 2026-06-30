# Crowd-Sourced Gym/Hotel Profiles (#971) — Disputed-Item Follow-Ups — Kickoff Handoff

**Session intent:** Forward-looking handoff scoping the **three optional follow-ups** flagged (not owed) when the Layer-2C disputed-item plan-gen slice shipped. #971 itself is **complete** (dedup + photos + admin-review + disputed-plan-gen all merged). None of these is a blocker; pick them up only if/when they earn their keep.
**Date:** 2026-06-30
**Predecessor (closing) handoff:** `handoffs/V5_Implementation_CrowdSourcedGymHotelProfiles_971_DisputedItemPlanGen_2026_06_30_Closing_Handoff_v1.md` — the slice these follow-ups extend.
**Design:** `designs/CrowdSourcedProfiles_DisputedItemPlanGen_971_Design_v1.md` (§2, §5, §9 list these as out-of-scope/possible follow-ups).
**Status:** No code this session — scoping only. The disputed-item slice itself is on branch `claude/crowd-sourced-gym-hotel-profiles-ip8w91` (PR opens + auto-merges on Andy's go).

---

## 1. Context the follow-ups build on

The shipped slice subtracts a peer-disputed equipment tag from the **plan-gen** equipment pool only (`locations.locale_effective_tags(..., exclude_disputed=True)`), leaving the locale UI showing the real shared set, with **lazy** invalidation (the disputed tag drops out at the next natural plan op via the content-addressed 2C cache key). Two consequences create the follow-up surface:

- The athlete still **sees** a disputed tag in their locale equipment view (plan-gen-only) — so there's room for a "this is under review" hint.
- An admin reviewing the dispute queue has **no signal of blast radius** — how many athletes inherit the profile a dispute touches.
- Lazy invalidation means an **already-generated** live plan keeps a disputed tag until its next refresh — fine by decision, but the proactive-eviction upgrade is pre-scoped should it ever bite.

Key reusable seam already in place: **`locations.disputed_equipment_tags(db, gym_profile_id) -> set[str]`** (union of open proposals' `removes`). All three follow-ups can lean on it.

---

## 2. Follow-up A — athlete-facing "under review" chip on a disputed tag

**What:** In the locale equipment editor, when a tag the athlete is inheriting is currently in the shared profile's **open-dispute `removes`** set, render a small "under review" chip next to it — so the athlete understands why the plan may not be building around a tag they can still see.

**Why:** Closes the plan-gen-vs-UI divergence the slice deliberately created (design §9 risk: "athlete sees the tag in their locale UI but the plan doesn't use it"). Pure UI; no plan-gen behavior change.

**Where (mechanically):**
- `routes/locales.py` `_edit_locale` GET — only the `shared_inherit` branch matters (a disputed proposal only exists against a *shared* base). Compute `disputed = locations.disputed_equipment_tags(db, shared['id'])` (the import + helper already exist) and pass it to the template alongside the existing `shared_tags` / `adds` / `removes`.
- `templates/locales/form.html` — the chip block at the `{% if mode == 'shared_inherit' %}` tag loop (≈ lines 79–82, where `+ override` / `– override` / `shared` chips render). Add a branch: `{% if tag in disputed %}<span class="chip warn" title="A peer flagged this as wrong; it's under admin review and won't drive your plan meanwhile">under review</span>{% endif %}`. Decide chip ordering vs. the existing `shared`/override chips (a disputed tag can also be `shared`).

**Effort:** Low (1 route line + 1 template branch + a render test). **Not a stop-and-ask trigger** (UI only).

**Gut check:** Confirm the desired interaction when the *viewing* athlete is the one who filed the dispute (they have a personal `remove` override → the tag shows the `– override` chip already; the disputed chip may be redundant for them but correct for everyone else). Probably show both or suppress "under review" when `tag in removes` for this viewer.

---

## 3. Follow-up B — admin signal of how many inheritors a dispute affects

**What:** In the admin gym-profile-edits queue, show per-profile **inheritor count** — how many athletes link that shared profile — so the operator can gauge a dispute's blast radius before approving/rejecting.

**Why:** A dispute on a 1-inheritor profile is low-stakes; one on a 40-inheritor commercial-chain gym is not. The queue currently shows the proposals + shared tags but no reach (design §9: "no admin-facing signal of how many inheritors a given open dispute is affecting").

**Where (mechanically):**
- `routes/locales.py` `_list_pending_profile_edits` — each queue entry already carries `{id, display_name, category, shared_tags, proposals}`. Add `inheritor_count`: `SELECT COUNT(*) FROM locale_profiles WHERE gym_profile_id = ?` per profile (or one grouped query over the queue's profile ids to avoid N+1). Note this counts **locale links**, not distinct users — decide which you want (a user can link the same profile at multiple locales; distinct-user count = `COUNT(DISTINCT user_id)`).
- `templates/admin/gym_profile_edits.html` — render the count near the `display_name` header (≈ line 33).

**Effort:** Low–medium (1 query + 1 template line + a test on the count). **Not a stop-and-ask trigger** (admin read-only UI).

**Gut check:** Decide locale-link count vs. distinct-user count up front (the more honest "blast radius" is distinct users). Keep it one query, not per-row, if the queue is large.

---

## 4. Follow-up C — proactive cross-inheritor eviction (the rejected fork-2 option)

**What:** When a dispute is **filed or withdrawn** (Slice 3 `_record_profile_edit`) — and optionally on admin review — evict the Layer-2C caches of **all** athletes inheriting that profile, so their next plan op re-derives immediately instead of waiting for a natural refresh.

**Why / when:** Only if lazy invalidation proves too slow in practice — i.e. an already-generated live plan keeping a disputed tag "too long" becomes a real complaint. This is the **additive upgrade path** the design pre-scoped (§5, §9); it does not replace any shipped behavior.

**Where (mechanically):**
- The per-user eviction primitive exists: `routes/locales._evict_layer2c_on_equipment_change(db, uid)` → `evict_on_layer_change(cache, uid, 'layer2c')`. The new work is the **fan-out**: resolve every `user_id` whose `locale_profiles.gym_profile_id` = the disputed profile (`SELECT DISTINCT user_id FROM locale_profiles WHERE gym_profile_id = ?`) and evict each.
- Call sites: `_record_profile_edit` (file/withdraw) and, if wanted, the admin approve/reject path (`routes/admin.py` `review_gym_profile_edit`). Note **approve already** mutates the shared `equipment` and is a separate equipment-change — verify whether it already fans out to inheritors or also relies on lazy (worth confirming as part of this work; it may be a pre-existing lazy gap, not new).

**Effort:** Medium (new fan-out helper + wiring at 1–2 call sites + tests). **This re-litigates a ratified decision (fork 2 = lazy) → stop-and-ask trigger #3 (invalidation rule) — do NOT build without Andy re-confirming**, since the explicit decision was *against* proactive eviction. The cost it reintroduces: one peer's provisional flag churning every inheritor's live plan at a busy gym.

**Gut check:** Before building, get a real signal that lazy is insufficient (Rule #14 — don't infer; if "stale disputed tag in a live plan" isn't observable, instrument it first). The decision was deliberate; reversing it needs evidence, not anticipation.

---

## 5. Suggested ordering

A and B are cheap, independent, UI-only wins that improve the dispute UX for both the athlete and the admin — do them together in one small within-ceiling slice if/when the dispute feature gets real use. C stays parked behind a real-world signal + an Andy re-confirm. If none of these surfaces as a need, **#971 is simply done** and these can stay as documented backlog.

---

## 6. Operating notes

1. **Read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff (or the closing handoff it extends) → `./scripts/verify-handoff.sh`.
2. **No schema / no Neon-apply** for A or B (read-only over existing tables). C adds no schema either (eviction only).
3. These three are recorded in `CARRY_FORWARD.md` under #971 as optional, non-owed follow-ups pointing here.

---

**End of handoff.**
