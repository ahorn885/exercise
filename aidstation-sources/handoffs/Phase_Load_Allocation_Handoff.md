# Phase Load Allocation Audit — Handoff (post-prep)

**Date:** 2026-05-05
**Status:** Pre-audit prep complete. 5 of 18 sports fully ready. 13 sports + LDC deferred work await audit sessions.
**Source files in project:**
- `Sports_Framework_v3.xlsx` (canonical data; updated this thread)
- `Athlete_Onboarding_Data_Spec_v2.md` (consumer of framework)
- `V2_Handoff_post_open_items.md` (parent handoff that authorized this work)
- `Layer0_ETL_Spec.md` (downstream ETL — not yet reviewed against new schema)

---

## Where things stand in one paragraph

The framework has 18 sports across Sheet 1 (Sports Index), Sheet 3 (Sport × Discipline Map), and Sheet 5 (Phase Load Allocation). This thread completed the structural prep work: collapsed Off-Road Multisport variants into one entry, normalized 4 packed-cell sports (Swimrun, Biathlon, XC Skiing, Skimo), canonicalized sport names across sheets, added an Applicability column to Sheet 3 (INCLUDED / EXCLUDED), migrated Sheet 5 to numeric low/high columns per phase, split Marathon and Ultramarathon into sub-format-specific entries (3 and 2 sub-formats respectively), and rebalanced their values to sum-to-100. **The data is now in a normalized shape that can support proper audit work.** Five sports are clean and ready (Marathon ×3, Ultramarathon ×2). Long Distance Cycling sub-format expansion is deferred to its own audit session. The remaining 13 sports need verification audits against authoritative sources.

---

## Locked decisions (do not relitigate)

### Q1 — Discipline-list policy
Mirror structure across all sports. Single **Applicability** column on Sheet 3 with two states: `INCLUDED` / `EXCLUDED`. The third state I had proposed (SUPPORT_ONLY) was dropped — supporting prep (e.g., rifle-stabilizer work for Biathlon) lives in the relevant sport's Strength row Notes. The app does not prescribe skill-only drills (shooting, fencing, archery, etc.); it only prescribes physical prep that supports those skills.

### Q2 — Sub-format granularity
Sub-format-specific rows. Sub-formats are encoded via **sport name suffix** in all three sheets (e.g., `Marathon (Road)`, `Marathon (Trail)`, `Marathon (Mountain)`). Per-discipline %s shift across sub-formats; only Triathlon's existing data violates this (sub-format variation expressed only in TOTAL hours) — Triathlon needs audit attention.

### Q3 — Cell format
Numeric low/high columns. Sheet 5 has 8 numeric phase columns (BASE_Low, BASE_High, BUILD_Low, BUILD_High, PEAK_Low, PEAK_High, TAPER_Low, TAPER_High). Sheet 3 col 9 (Phase Load) stays text format as a human-readable summary. **Open:** if any consumer prompt reads from Sheet 3 col 9 expecting numeric, that needs Sheet 3 migration too.

### Q4 — Source policy (audit-time)
Tier 1: peer-reviewed periodization studies, federation/governing-body coach education. Tier 2: established coach books (Friel, Daniels, Magness, Allen & Coggan), credentialed coach blogs. Tier 3: athlete training logs from credible competitors, reputable magazines — only with triangulation. Reject: uncredentialed blogs, AI-generated content. **Audit log records source tier per claim.**

### Q5 — Vertical gain parallel metric
Full progression tables for: **Skimo, Mountain Running, XC Skiing, Fell Running**. Notes-column reference only (no progression table) for: **AR, Off-Road Multisport, Marathon (Mountain), Ultramarathon (Trail)** — these have variable vertical demands per event.

### Q6 — Course-variant adjustments
Categorical Flat / Hilly / Heavy Vert (athlete picks; system stores per-sport thresholds in audit log as help text). Andy explicitly rejected hilly-vs-flat sub-formats for ultras ("almost all ultras have hills") — this stays a Notes-column adjustment, not a sub-format split.

### Q7 — Strength
Every sport gets a Strength row. Allocation bands by sport family (endurance-pure 5–10% Base; multisport 8–12% Base; pack/mountain 12–18% Base; skill-heavy 8–12% Base + skill maintenance separate).

### Q8 — Cross-sport consistency review
Final 30 min of Session 5. Validate that shared disciplines (D-001 Trail Running across sports) have coherent values where reasonable.

---

## What's done in `Sports_Framework_v3.xlsx`

### Sheet 1 — Sports Index
- 21 sport entries (was 18; Ultra split into 2, Marathon into 3)
- Canonical sport names locked

### Sheet 3 — Sport × Discipline Map
- 71 discipline rows
- New `Applicability` column (col 4): `INCLUDED` / `EXCLUDED`
- 1 EXCLUDED row in production: Ultramarathon (Trail) → Mountaineering / Scrambling
- Marathon and Ultramarathon split into sub-format-specific rows
- Off-Road has Road Cycling row (was missing)
- Swimrun split into Swim / Trail Running / Swimrun (Combined)

### Sheet 5 — Phase Load Allocation
- 124 rows
- Numeric low/high columns per phase (8 phase columns + Notes)
- 5 sub-formats with verified sum-to-100 (Marathon ×3, Ultramarathon ×2)
- 2 rows still flagged `AWAITING NORMALIZATION`: LDC R98 (XC MTB) and R99 (Enduro) — deferred per Andy's call to LDC dedicated session

### Cross-sheet
- Canonical names: `Ultramarathon (Trail)`, `Ultramarathon (Road)`, `Marathon (Road)`, `Marathon (Trail)`, `Marathon (Mountain)`, `Long Distance / Endurance Cycling`, `Cross-Country / Nordic Skiing`, `Canoe / Kayak Marathon`, `Skimo` (parenthetical descriptor moved to Sheet 1 col 2)

---

## What's open — audit sessions in priority order

Estimated **20–30 hrs total** across 5–6 sessions of 4–5 hrs each.

### Session 1 — Group A: Pure running sports (4 sports/sub-formats)
- **Marathon (Road)** — verify against Daniels, Magness, Pfitzinger; values are best-derived defaults, not literature-confirmed
- **Marathon (Trail)** — verify against ATRA / ITRA materials
- **Marathon (Mountain)** — verify against WMRA materials, mountain marathon coach blogs
- **Ultramarathon (Trail)** — verify against ITRA, UTMB coach materials, CTS ultra material
- **Ultramarathon (Road)** — verify against IAU, Comrades-specific materials
- **Mountain Running / Skyrunning** — clean structurally; verify
- **Fell Running** — clean structurally; verify

### Session 2 — Group B: Triathlon family (4 sports)
- **Triathlon** — has known structural issue: per-discipline %s currently constant across Sprint/Olympic/70.3/IM. Per Q1 decision, %s should shift. Likely needs sub-format expansion similar to Marathon/Ultra.
- **Duathlon** — verify; check if sub-format expansion needed
- **Aquathlon** — verify
- **Aquabike** — verify

### Session 3 — Group C: Water sports (3 sports)
- **Swimrun** — newly normalized; verify against ÖTILLÖ coach materials
- **Canoe / Kayak Marathon** — clean structurally; verify against ICF
- **Open Water Marathon Swimming** — clean structurally; verify against World Aquatics

### Session 4 — Group D: Snow + skill-hybrid (4 sports)
- **Skimo** — newly normalized; verify against ISMF
- **Cross-Country / Nordic Skiing** — verify
- **Biathlon** — newly normalized; verify against IBU. Check Q1 implementation in Shooting row.
- **Modern Pentathlon** — needs significant audit. Pre-existing sum-to-100 issue: Taper drops to 63%. Post-2025 format (Fencing → OCR → Swim → Laser Run) has limited periodization literature; expect Tier 3 sources.

### Session 5 — Group E + cleanup (2 sports + cross-cutting)
- **Long Distance / Endurance Cycling** — biggest single piece of work. 4 sub-formats need expansion (Road Endurance, Gravel Ultra, XC MTB, Enduro). Currently sums to ~270% because rows are alternatives but treated as additive. R98/R99 still AWAITING NORMALIZATION.
- **Off-Road / Adventure Multisport (Non-Nav)** — verify free-form approach
- **Cross-sport consistency pass** (Q8) — final 30 min

### Session 6 (if needed) — overflow + spec touchups
- `Athlete_Onboarding_Data_Spec_v2.md` §C footnote: acknowledge that Conditional/Cross-train/Alternative rows must be zeroed before sum-to-100 validation
- `Layer0_ETL_Spec.md` review against numeric Sheet 5 schema
- AR re-validation (existing data shows Build 122% / Peak 124% — Conditional flags may be miscategorized in current data)

---

## Pre-existing sum-to-100 issues (audit-time work)

| Sport | Acute issue | Likely cause |
|---|---|---|
| LDC | All phases ~270% | Sub-format rows treated as additive; structural fix needed |
| Modern Pentathlon | Taper 63% | Skill-heavy taper; existing values may not capture full picture |
| AR | Build 122% / Peak 124% | Conditional pattern detection may be missing flags; existing data integrity worth re-checking |
| Skimo | Taper 70% | Race-day taper structure; verify against ISMF |
| Most others | ±15% of 100 | Standard audit refinement |

**These are not bugs introduced this thread.** The data was inconsistent before. Each gets resolved in its sport's audit session.

---

## Schema and naming conventions (locked)

- **Sport name format:** `Sport Name (Sub-format)` for sports with sub-formats. No newlines except where existing entries use them as line wrap (e.g., `Off-Road / Adventure\nMultisport (Non-Nav)`).
- **Sheet 5 columns:** 1=Sport, 2=DiscID, 3=Discipline, 4=Role, 5=BASE_Low, 6=BASE_High, 7=BUILD_Low, 8=BUILD_High, 9=PEAK_Low, 10=PEAK_High, 11=TAPER_Low, 12=TAPER_High, 13=Notes
- **Sheet 3 columns:** 1=Sport, 2=DiscID, 3=Discipline Name, 4=Applicability, 5=Role, 6=Race%, 7=Sport-Specific Context, 8=B2B Pairing, 9=Phase Load (text, denormalized)
- **Cell formatting:** body rows use sport-specific fill; TOTAL rows use 1F4E79 dark blue with white bold text; AWAITING NORMALIZATION rows have notes prefixed with that string verbatim
- **Conditional rows:** marked with role suffix `(*Conditional)` and notes prefixed `*CONDITIONAL — REPLACES ... volume, NOT additive.` Sum-to-100 validation must zero these out.
- **Vertical gain metric:** lives in row Notes column for sports where applicable

---

## How to start the next thread

1. Confirm the project files include `Sports_Framework_v3.xlsx` and this handoff. If the parent `V2_Handoff_post_open_items.md` is also present, that's bonus context.
2. State: "Resume Phase Load Allocation audit. Reference `Phase_Load_Allocation_Handoff.md` in project. Begin Session 1 — Group A (running sports)."
3. Tell Claude to attach `Sports_Framework_v3.xlsx` to the new thread (project search returns docs about it but cannot read arbitrary cells).
4. Confirm the audit log doc structure from §7 of `Phase_Load_Allocation_Audit_Scope.md` (per-sport: source list, derivation reasoning, departures from sport-group median, open questions). Create `Phase_Load_Allocation_Audit_Log.md` as an empty side doc at start of Session 1.

---

## Honest gut check before closing this thread

**Three things worth one more look before Session 1 starts:**

1. **The LDC sub-format issue (~270% sum) is the single biggest audit task.** It's not just verification — it's structural normalization (5 sub-format rows currently summed as additive must be split into separate sport entries: `Long Distance / Endurance Cycling (Road)`, `(Gravel Ultra)`, `(XC MTB)`, `(Enduro)`). Plan for 3–4 hrs on LDC alone in Session 5.

2. **AR's Build 122% / Peak 124% is suspicious.** Either the existing data has real issues, or my Conditional-detection filter missed flags during the sum check. Worth a 15-min targeted check at the start of any session that touches AR-adjacent data. AR is the worked example — if it's wrong, the template propagates wrong.

3. **Triathlon's per-discipline % being constant across sub-formats violates Q1.** Andy confirmed %s should shift. Triathlon will need sub-format expansion similar to what Marathon and Ultramarathon got. This adds scope to Session 2 — budget accordingly.

**Strongest argument against the audit plan:** auditing all 18 sports (now 21 with sub-format splits) pre-launch is a lot of work. If user analytics post-launch show concentrated demand on 4–5 sports, the audit-everything-pre-launch effort isn't recovered. The handoff's decision #8 was "full pre-launch audit" — that's been re-confirmed multiple times — but worth logging once for the record that the lean alternative exists.

---

## File state at handoff

- `Sports_Framework_v3.xlsx` — current canonical, in project
- Backups (in case revert needed): `Sports_Framework_v3.backup.xlsx`, `.pre-migration.backup.xlsx`, `.pre-scope-reveal.backup.xlsx`, `.pre-fix.backup.xlsx` — these were intermediate working backups, not committed; if Andy needs any of them, they can be regenerated from git history of this thread's outputs.
