# Vocab Patch — K New Equipment Entries (v3 — final)

**Status:** Locked. All user decisions from this session applied.

Proposes **10 new canonical entries** for `Vocabulary_Audit_v2.md` Section 3 and `layer0.equipment_items`. Companion populate SQL: `populate_equipment_items_K_additions.sql`.

---

## Changes from v2

- **Stairs** added as new vocab entry (Bodyweight & Portable category). Per user clarification, "Stairs" means a full flight of stairs (not universal). Single-step / step-up / stair-edge usage is now treated as universal (no equipment, no improvised flag).
- **Backpack** is now treated as canonical equipment in ALL substitute entries (not improvised). 32 substitute groups now reference Backpack; 35 reference Weighted vest as alternative load.
- Schema now uses **AND-OR** structure (`equipment_required: list[list[str]]`) — outer = OR, inner = AND. Enables Goblet squat (DB or KB), stair-climb-with-pack (Stairs+Backpack OR Stairs+Vest), and similar disjunctive cases.

---

## Confirmed parser-side renames (baked in)

`Rack` → `Squat rack` · `TRX` → `TRX / suspension trainer` · `Weight plate` → `Weight plates` · `Sliding disc` → `Slider discs` · `Ski ergometer` → `Ski erg` · `Cable row machine` → `Seated row machine` · `Arm bike` → `Arm bike / UBE` · `GHD machine` → `Glute ham developer (GHD)` · `Nordic ski ergometer` → `Ski erg`

## Confirmed parser-side collapses (baked in)

`Balance pad` → `Foam pad` · `Doorway pull-up bar` → `Pull-up bar` · `Prowler` → `Weighted sled`

## Reverted (kept separate)

`Hyperextension bench` stays as new entry (NOT collapsed to GHD)

## Removed (won't track)

`Pistol training equipment` — AR doesn't include shooting

---

## 10 new vocab entries

### Stability & Balance — `Wobble board`
Hard wood/plastic balance trainer. Distinct from BOSU ball, Balance disc, Foam pad. **3 usages**.

### Plyo & Power — `Mini hurdles`, `Mini trampoline`
- Mini hurdles: agility hurdles ~6"–12". 1 usage.
- Mini trampoline: rebounder. 1 usage.

### Bodyweight & Portable — `Ab straps`, `Stairs`
- Ab straps: hanging knee/leg raise loops. 1 usage.
- **Stairs**: full flight of stairs (multi-step). NOT universal. Distinct from Stair climber machine. 10 usages (6 raw stair entries; expanded to 10 via Backpack/Vest disjunction in stair-with-pack cases).

### Recovery & Therapy — `Stick roller`
Handheld muscle roller. 1 usage.

### Sport-Specific — Climbing — NEW category — `Climbing holds`, `Climbing rope`
- Climbing holds: wall-mounted training holds. 1 usage.
- Climbing rope: rope climb training. 1 usage.

### Sport-Specific — Winter — `Rollerskis`, `Inline skates`
- Rollerskis: dryland XC. 3 usages.
- Inline skates: skating dryland. 2 usages.

### Machines — Lower Body — `Hyperextension bench`
45-degree posterior chain bench. Distinct from GHD. (Captures "Hyperextension Bench" and "Reverse Hyper" patterns.)

---

## Schema impact

See `populate_equipment_items_K_additions.sql` — bundled INSERTs for the 10 entries. Idempotent via ON CONFLICT.

---

## §J onboarding impact

User decision: **Option 1 — always show.** The 10 new entries get checkbox visibility in the §J equipment picker.

---

## AND-OR schema in equipment_substitutes_structured

The equipment_required field is now `list[list[str]]` (CNF semantics):

| Form | Meaning | Example |
|---|---|---|
| `[]` | No equipment required (bodyweight or fully improvised) | `[]` for "Bodyweight squat (no load)" |
| `[["X"]]` | Single equipment required | `[["Dumbbell"]]` for "DB Romanian Deadlift" |
| `[["X"], ["Y"]]` | X OR Y satisfies | `[["Dumbbell"], ["Kettlebell"]]` for "Goblet squat" |
| `[["X", "Y"]]` | Both X AND Y required | `[["Stairs"]]` for "Hotel stairs at sustained effort" |
| `[["X", "Y"], ["X", "Z"]]` | (X+Y) OR (X+Z) | `[["Stairs", "Backpack"], ["Stairs", "Weighted vest"]]` for "Stair climb with pack" |

Layer 1 Node 2C Tier 2 satisfaction:

```
substitute_available =
    is_improvised AND equipment_required is empty
    OR
    ANY group in equipment_required satisfies (group ⊆ athlete_pool)
```

Note: `is_improvised=true` no longer bypasses equipment requirements. It is a coaching signal (Layer 4 can prescribe with "use improvised setup" cue) but the equipment must still match.

---

## Final substitute classification stats

| Category | Count | % of 511 |
|---|---|---|
| Equipment only (no improvised) | 204 | 40% |
| Improvised only (no equipment) | 240 | 47% |
| Both equipment + improvised | 23 | 4% |
| Bodyweight (neither) | 44 | 9% |
| **Disjunctive (multi-OR-group)** | **33** | **6%** |

---

## Open question on EX193 (still pending action)

EX193 (Shooting Breath Control & Stance) should be deleted from the next exercise database iteration since AR doesn't include shooting. Out of scope for this K work; track as a v18 to-do.
