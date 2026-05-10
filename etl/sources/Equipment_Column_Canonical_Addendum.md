# Equipment Column Addendum — Canonical Gear Toggle Principle
*Patch to AR_Exercise_Database_Documentation.md, Section 7 (Column 7: Equipment). Supersedes prior guidance where it conflicts.*

---

## Core Principle (load-bearing, locked)

**Equipment tokens are canonical gear toggles meaningful for plan generation only.**

The equipment[] field answers exactly one question at runtime: *does the athlete have the physical object needed to perform this exercise?* Nothing else belongs here.

This distinction is architectural. The ETL pipeline uses equipment tokens to filter exercises against the athlete's declared gear inventory. Tokens that are not gear toggles pollute this filter with false positives, false negatives, and unmaintainable vocabulary.

---

## What IS a valid equipment token

A token belongs in the equipment column if and only if:
- It is a **discrete physical object** the athlete must own or have access to
- Its **presence or absence would prevent the exercise from being performed** as described
- It is **meaningful across multiple athletes** — not specific to one athlete's configuration

Examples of valid tokens:
- `Barbell`, `Dumbbell`, `Kettlebell`, `Resistance band`
- `Mountain bike`, `Road bike`, `Bike trainer`, `TT Bike`, `Gravel bike`
- `Packraft`, `Kayak`, `SUP`, `Canoe`
- `Climbing gear` (aggregate: harness, rope, belay device, carabiners, slings, anchor hardware)
- `Mountaineering kit` (aggregate: crampons, ice axe, mountaineering boots, ski crampons)
- `XC ski kit`, `Touring ski kit`
- `Trekking Poles` (distinct from ski poles — ski poles fold into ski kit aggregates)
- `Climbing Wall` (venue toggle — athlete must have access to a climbing gym or rock wall)
- `Pull buoy`, `Pool`
- `Plyo box`, `Weighted vest`, `Cable machine`, `Squat rack`
- `Rice bucket`, `Pinch Block`, `Wrist Roller` (grip training equipment)
- `Snowshoes`, `Backpack`

---

## What is NOT a valid equipment token

Do not add any of the following categories to the equipment column:

| Category | Examples | Reason |
|---|---|---|
| **Universal venues** | Floor, Wall, Track, Open Space, Outdoor | Always available — no toggle value |
| **Athlete-choice clothing** | Wetsuit, Running Shoes, Headlamp, Soft Flask, Knee Pad, Gloves | Athlete decides; not a plan-generation constraint |
| **Universal AR navigation gear** | Compass, GPS, Topographic Map | Assumed universal in AR context |
| **Sub-components of canonical kits** | Belay Device, Rope, Harness, Carabiners (individually) | Aggregated into `Climbing gear` |
| **Configuration qualifiers** | Loaded Backpack, Loaded Touring Bike, Inclined Treadmill | Describe setup, not equipment |
| **Consumables** | Chews, Gels, Cups | Not gear |
| **Exercise props with no availability constraint** | Cones (for agility drills) | Athlete can improvise; no toggle value |
| **Anchor point (for bodyweight exercises)** | Anchor Point (Nordic Curl, GHD) | Exercise-specific attachment — too ambiguous and not a plannable gear item |
| **Skill prerequisites / technical contexts** | Snow Slope, Whitewater, Groomed Track, Gravel Road, Open Water, Darkness | Environmental conditions, not athlete gear |

---

## Canonical vocabulary — v19 reference

This is the current approved token list as of v19. Only these tokens (or new ones explicitly approved via a vocabulary decision) may appear in the Equipment column.

*Strength / conditioning:*
Barbell, Squat rack, Dumbbell, Kettlebell, Resistance band, Pull-up bar, Dip bars, Rings, Plyo box, Weighted vest, Cable machine, Smith machine, Leg press machine, Leg curl machine, Glute-Ham Developer (GHD), Hip thrust machine, Calf raise machine, Lat pulldown machine, Seated row machine, Pec deck machine, EZ-curl bar, Swiss bar, Trap bar, Safety bar, Landmine attachment, Sandbag, Weight plates, Pinch Block, Wrist Roller, Rice bucket, Wrist Roller, Incline Board, Battle ropes, Slam ball, Medicine ball, Stability ball, Foam roller, Lacrosse ball, Massage gun, Suspension trainer (TRX)

*Cardio / endurance equipment:*
Treadmill, Stationary bike, Road bike, Mountain bike, TT Bike, Gravel bike, Bike trainer, Rowing machine, Ski erg, Elliptical, Paddling ergometer

*Outdoor / expedition:*
Backpack, Trekking Poles, Snowshoes, Mountaineering kit, XC ski kit, Touring ski kit, Climbing gear, Climbing Wall

*Water:*
Kayak, Packraft, Canoe, SUP, Pool, Pull buoy, Rowing Shell

*Misc:*
Pull buoy, Jump rope

---

## Aggregation rules

**Climbing gear** covers: Harness, Rope, Belay device, Carabiners, Slings, Fixed rope, Anchor hardware, Mechanical ascender, Via Ferrata Y-lanyard. Use this aggregate — do not list sub-components individually.

**Mountaineering kit** covers: Crampons, Ice axe, Mountaineering boots, Ski crampons. Use this aggregate.

**XC ski kit** covers: Cross-country skis (classic or skate), ski poles for XC skiing. Use this aggregate — ski poles do NOT appear separately.

**Touring ski kit** covers: Touring skis, touring ski boots, climbing skins, ski crampons, alpine skis. Use this aggregate — ski poles do NOT appear separately.

**Trekking Poles** — separate canonical, not part of any ski aggregate. Used for hiking, trail running with poles, snowshoeing.

---

## Disjunction encoding

The Equipment column is a flat comma-separated list with AND semantics by default (athlete needs all listed items). When multiple alternatives are valid for the same exercise, list them all:

`Dumbbell, Kettlebell` means either works (OR semantics at runtime — the athlete needs at least one).

Do not use " or " syntax in the column. Do not use compound tokens like "Dumbbell or Kettlebell". List each alternative as a separate comma-separated token.

---

## When to leave Equipment blank

Leave the Equipment column empty if and only if the exercise is genuinely bodyweight — no equipment of any kind is needed or helpful. Empty does not mean "equipment unknown"; it means "no equipment required."

If the exercise *can* be done bodyweight but can *also* be loaded, list the loading equipment (e.g., `Dumbbell, Kettlebell, Weighted vest`). The athlete's onboarding inventory determines which variant they'll be assigned.
