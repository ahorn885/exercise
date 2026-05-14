# Vocab Pass — Handoff Note (mid-session)

**Date:** May 2026
**Status:** Vocab self-pass mostly complete. Decisions locked on gear-readiness abstraction and systemic constraints merge. Doc revision + Section B fix not yet executed.
**Pickup file:** `Vocabulary_Audit_v1.md` (in /mnt/user-data/outputs)

---

## Where we are

Working session order locked at start:

1. ✅ Vocab self-pass (in progress — needs one more revision pass per below)
2. ⏸ v1 confirmation pass on unchanged sections (G, H, M, N)
3. ⏸ v2 spec writing in batches

Vocab pass produced `Vocabulary_Audit_v1.md` with body parts (41 canonical), systemic constraints (6 athlete-side), equipment canonical list, required changes summary, and no-equipment fallback logic. Doc was iterated once after Andy's feedback on climbing items / race nutrition / terrain UX. A second iteration is now needed per below.

---

## Decisions made this session

### Body parts (Option B — hybrid naming)

- Common-name where it adds no precision over anatomical (Lumbar → Lower back, Cervical → Neck, Thoracic → Upper back).
- Anatomical retained where athletes know the term from PT (Achilles, Plantar fascia, IT band, Soleus, Peroneal, Meniscus, ACL/PCL/MCL/LCL, TFL).
- Sub-region precision unioned from proposed handoff list + col 13.

### Systemic Constraints (Option A originally, now superseded — see "Open decisions")

- Originally: separate field on Injury Record (B.1).
- Andy's question at end of session: should this merge with Chronic Medical Conditions instead?
- **Claude's recommendation: yes, merge.** ~70% overlap. Proposed structure: replace both fields with a single "Health Conditions" record-type field (parallel to Injury Record), with fields: System category (enum), Name (free text), Status (Current / History), Notes (free text).
- **Andy did not explicitly confirm the merge before stopping.** Pick this up first thing tomorrow.

### Equipment vocab

- Slash-strings ("Kayak / Packraft") decompose to atomic items + OR-logic at matching engine.
- "Assumed universal" category for items always available: Bodyweight, Floor, Wall, Doorway, Anchor point, Compass, Topo map, GPS, Outdoor space.
- Over-collected items dropped: Jacob's Ladder, Compression boots, Sauna, Stretch strap.
- Race nutrition items (Gels, Chews, Cups, Soft flask) NOT tracked. Move from col 7 to col 10 Notes or drop.
- Equipment + terrain collected in same UX flow at locale-add (data structure stays separated: equipment under Account Config, terrain under Section K).

### Gear-readiness toggle (sharpened end of session)

Originally: "abstract accessories under readiness toggle, keep top-level items individually asked."

**Andy's clarification at end of session:** Don't track sub-items AT ALL — not in col 7, not in onboarding. Single token in col 7 for whole-kit categories, matching one-to-one with readiness toggle.

**Sport-by-sport application of this rule (Andy's last message):**

| Sport-kit category | Treatment | Status |
|---|---|---|
| Climbing gear (roped) | Single col 7 token. Rolls up rope, harness, belay device, carabiners, slings, anchor hardware. | ✅ Confirmed |
| Bouldering gear | Single col 7 token. | ✅ Confirmed (by extension) |
| Rappelling / abseiling gear | Single col 7 token. | ✅ Confirmed (by extension) |
| Via ferrata gear | Single col 7 token. | ✅ Confirmed (by extension) |
| Mountaineering gear | Single col 7 token. Rolls up crampons, mountaineering boots, ice axe, mountaineering harness. | ✅ Confirmed |
| Fencing gear | Single col 7 token. | ✅ Confirmed (by extension) |
| Shooting gear | Single col 7 token. | ✅ Confirmed (by extension) |
| Whitewater paddling gear | Single col 7 token. Rolls up spray skirt and other whitewater accessories. Vessel (kayak / canoe / packraft) stays separate. | ✅ Confirmed (by extension) |
| **Skiing gear** | **Single col 7 token. Rolls up skis (touring/AT, classic XC, skate XC, alpine, rollerskis), ski boots, ski poles, climbing skins, ski crampons, boot buckles.** | ✅ Confirmed (Andy's last message) |
| Snowshoes | **Stays separate as its own item.** Different concept — not part of "skiing gear." | ✅ Confirmed (Andy's last message) |
| Avalanche safety | Stays separate (it's a safety gate, not a gear category). | ✅ Implicit retained |

The principle Andy stated: "winter gear that matters stays together. Like skis, ski boots, and poles are all 'skiing gear' but something like snow shoes are a different idea entirely."

**Generalised principle:** kit that's always used together for one mode of travel = single toggle/token. Distinct travel modes = distinct tokens. Accessories within a single mode roll up; vessels/footwear that switch the mode of travel stay individual.

### Top-level items still asked individually (no rollup)

| Sport | Items kept distinct |
|---|---|
| Cycling | Road bike · Mountain bike · Gravel bike · TT bike · Power meter · Bike trainer |
| Paddle | Kayak · Canoe · Packraft · SUP · Inflatable raft · Rowing shell · Paddle erg · Rowing erg |
| Running/Hiking | Running shoes · Hiking boots · Trekking poles · Backpack · Weighted vest · Headlamp |
| Winter | Snowshoes · Avalanche safety gear |
| Swimming | Wetsuit · Pull buoy · Kickboard · Swim paddles · Swim fins |

---

## What needs to happen tomorrow (in order)

### 1. Confirm the Health Conditions merge

Single question to start: does Andy agree to merge Chronic Medical Conditions + Systemic Constraints into one "Health Conditions" record-type field (per Claude's recommendation)? Or keep them separate per original Option A?

If merge: structure is Name + System Category + Status + Notes, parallel to Injury Record.
If separate: keep Section B as-is with both fields, flag the overlap as accepted redundancy.

### 2. Revise Vocabulary_Audit_v1.md

Apply the sharpened gear-readiness rule throughout the doc:

- Equipment canonical list: replace itemized winter/climbing/mountaineering/whitewater/fencing/shooting entries with single "Skiing gear", "Climbing gear (roped)", "Bouldering gear", "Rappelling gear", "Via ferrata gear", "Mountaineering gear", "Whitewater paddling gear", "Fencing gear", "Shooting gear" tokens.
- Layer 0 cleanup tasks: add a new task — collapse all sub-component col 7 tokens into the single rolled-up token per category. List all the col 7 tokens going away (rope, harness, belay device, carabiners, slings, anchor hardware, mechanical ascender, via ferrata Y-lanyard, crampons, mountaineering boots, ice axe, mountaineering harness, climbing skins, ski crampons, boot buckles, classic/skate XC ski distinctions if rolled into "Skiing gear" — TBD whether classic vs skate is one toggle or two).
- Open question to resolve while revising: are classic XC and skate XC the same "Skiing gear" toggle, or distinct? Same kit but different technique. Recommend: same toggle (gear is interchangeable for an athlete who skis both); the technique distinction lives in sport selection (Section 1), not equipment.
- Update the "Sport-Specific Gear Readiness" toggle list in v2 spec: the toggle list IS the canonical kit-category list. They're now one-to-one with col 7 tokens.

### 3. Then execute Section B fix

Per Andy's instruction: "Lets fix the injury bit now. what do we need to do?"

Scope (already proposed in chat):

1. Apply canonical body parts to B.2 (replacement, not edit)
2. Add Injury Type field to B.1 (per handoff Section B decision — already on the list)
3. Apply Health Conditions decision from Step 1 above (merge or separate)
4. Confirm Movement Constraints (B.3) wording unchanged; flag col 9 Movement Components Layer 0 task as separate cross-layer item

Deliverable: a "Section B v2 batch" doc that slots directly into the v2 spec when we get there.

### 4. Then v1 confirmation pass on G, H, M, N

Quick pass through v1 sections that aren't mentioned in the original handoff to confirm "no changes" actually means no changes.

### 5. Then v2 spec writing in batches

Per the pass strategy locked at start of session: structural reorg + Sections A–B as first batch; reassess pace after.

---

## Files

- `Vocabulary_Audit_v1.md` — current vocab pass output (in /mnt/user-data/outputs). Needs revision per Step 2 above before being treated as final.
- This file — handoff note. Save to project for tomorrow's pickup.

---

## Open items still deferred (unchanged from session start)

| # | Item |
|---|---|
| 1 | Movement Components on col 9 (Layer 0 enhancement) |
| 2 | Connected Services entity detail (post-go-live per Andy's decision) |
| 3 | Disclosure language copy |
| 4 | Re-injury risk model |
| 5 | v2 structural reorg into Athlete Data / Account Config / Plan Management |
| 6 | Sheet 7 deprecation timing |
| 7 | Migration path from current app database |
| 8 | TA / aid station fallback behaviour |
| 9 | Race-specific fueling preferences vs lifestyle dietary separation |

Plus newly-deferred from this session:

| Item | Why deferred |
|---|---|
| Auto-population of merged Health Conditions (if merge confirmed) from Food Allergies/etc. | v2 spec design decision |
| Whether classic XC and skate XC are one "Skiing gear" toggle or two | TBD next session — current recommendation: one toggle |
| Layer 1 ↔ Layer 0 query layer spec (including no-equipment derivation logic) | Deferred until schema is built |
