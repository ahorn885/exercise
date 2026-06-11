# V5 Implementation — Skill-capability gating: substitute strength for unclaimed-skill disciplines (#336)

**Date:** 2026-06-11
**Branch:** `claude/upbeat-fermi-7bkkde` → **PR [#551](https://github.com/ahorn885/exercise/pull/551)**, squash-merged to `main` (`94ec454`)

## 1. What this session was

Issue [#336](https://github.com/ahorn885/exercise/issues/336) (high / safety; parent [#201](https://github.com/ahorn885/exercise/issues/201)): the `requires_skill_capability` signal was **computed in Layer 2C but gated nothing**, so plan-gen prescribed roped climbing + abseiling training to an athlete who never selected the roped-climbing skill (empirical: pv=46). Prescribing skill-dependent training the athlete hasn't claimed is a correctness AND safety problem. Related [#298](https://github.com/ahorn885/exercise/issues/298) flagged the same flag as emitted-but-unconsumed.

**Andy's decision (the design fork the issue deferred):** neither HITL-flag nor hard-exclude — **automatic substitution**. The discipline stays in the plan, but its skill-specific session is swapped for strength-and-conditioning work that builds the underlying capacity (grip / upper-body strength in place of a climbing session), with a coach note "prescribing strength until you're cleared on `<skill>`".

## 2. What shipped

**Key data finding that placed the fix:** `D-012 Rock Climbing`'s `exercise_db_sport` is "Adventure Racing" (per `sport_discipline_bridge`), so its 2C-resolved exercises are *already* general AR strength — the prescribed climbing/abseiling was **discipline-level sport sessions** the synthesizer emits because D-012 is an included discipline with load-weight, allocated by the deterministic session grid. So the gate lands at the **session level**, not the 2C exercise pool.

- **`layer4/validator.py`** — new deterministic rule `_rule_skill_capability_gate` (severity `blocker`, registered in `_ALL_RULES`, 22nd rule) + a shared helper `skill_gated_disciplines(layer2c_payloads) -> {discipline_id: toggle_name}`. The gate set is sourced from the Layer 2C `requires_skill_capability` coaching flags — **consuming the previously-orphaned flag (#298)**. The rule blocks any session with `kind == 'cardio'` tagged to a gated discipline; strength substitutions (kind `'strength'`, even tagged to the gated discipline) pass. `blocker` so the capped-retry loop drives the substitution — a surviving unsafe session is worse than a retry.
- **`layer4/per_phase.py`** — derive the gate set once in `render_user_prompt` and surface it to the synthesizer two ways: (a) a dedicated `_format_skill_capability_gates()` "Skill-capability gates" substitution directive, and (b) an inline `[SKILL-GATED: …]` annotation on the authoritative deterministic session grid (`_format_session_grid` gained a `skill_gated` kwarg) so the per-discipline count is read as a strength substitution. Imports `skill_gated_disciplines` from the validator.
- **`layer2c/builder.py`** — reworded the `requires_skill_capability` flag message toward substitution intent (metadata shape unchanged — still `{"toggle_name": …}`).
- **Tests:** `tests/test_layer4_validator.py` +7 (helper extraction, cross-locale dedup, blocks gated cardio, allows strength substitution, no-fire for ungated discipline, no-fire when no 2C payloads); `tests/test_layer4_strength_pool.py` +3 (directive renders / empty when nothing gated / id fallback without 2A).

The skill→discipline mappings come from `layer0.skill_capability_toggles` (`etl/sources/populate_skill_capability_toggles.sql`, 5 rows): `climbing_roped→D-012`, `via_ferrata→D-014`, `whitewater_handling→D-010`, `swim_open_water→D-004`, `mountaineering→D-018/D-022`. Toggles default **OFF** ("assume-not-skilled"), so until the capture surface is populated the gate fires for every included gated discipline — the safe failure mode, matching the issue's safety framing.

## 3. Verification

- Full suite green: `python -m pytest tests/ etl/tests/ -q` → **2351 passed, 30 skipped**.
- `tests/test_layer4_validator.py` → 111 passed (incl. the 7 new). `tests/test_layer4_strength_pool.py` → 14 passed (incl. the 3 new).
- **CI green on PR #551:** Python unit suite, JS harness, Layer 0 integrity gate, Vercel preview — all success; Real-LLM smoke skipped (no API key, expected). Squash-merged.

## 4. Owed / next move

1. **#336 — closed on merge** (PR body `Closes #336`).
2. **OWED — Andy's-hands Neon deploy (now load-bearing).** Run `etl/sources/run_owed_layer0_migrations.sql` (or `populate_skill_capability_toggles.sql` alone) on Neon to confirm the 5 active `skill_capability_toggles` rows exist — the gate is **data-driven** off that table, so an empty/absent table means the gate silently no-ops (no 2C flags → nothing gated). The script is idempotent with a self-verify (`EXCEPTION` if ≠5 active rows). Tracked in CARRY_FORWARD owed-deploys.
3. **Follow-on (capture surface, already filed in CARRY_FORWARD §"5 D-73 Phase 5.2 walkthroughs"):** the `/onboarding/skills` + `/profile?tab=skills` surfaces let athletes claim skills, which turns toggles ON and lifts the gate per discipline. Until walked, all gated disciplines substitute by default.
4. **Carried (unchanged):** go-live blockers **#539** (tab-closed plan-gen crawl) + **#540** (terrain-infeasible locale routing) remain top of the 4-tier order. #540 is adjacent (also a "don't prescribe what the athlete can't do" feasibility gate, terrain side).

## 5. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Skill-gate validator rule + helper | `layer4/validator.py` | `def skill_gated_disciplines`; `def _rule_skill_capability_gate` (`severity="blocker"`); `_rule_skill_capability_gate` in `_ALL_RULES` |
| Gate consumes the 2C flag (#298) | `layer4/validator.py` | `skill_gated_disciplines` iterates `coaching_flags` where `flag_type == "requires_skill_capability"` |
| Synthesizer substitution directive | `layer4/per_phase.py` | `def _format_skill_capability_gates`; `=== Skill-capability gates`; `skill_gated=` kwarg on `_format_session_grid`; `[SKILL-GATED:` inline marker |
| 2C flag reworded to substitution | `layer2c/builder.py` | `requires_skill_capability` message "Substitute strength-and-conditioning … until the skill is cleared (#336)"; metadata still `{"toggle_name": …}` |
| Tests | `tests/test_layer4_validator.py`, `tests/test_layer4_strength_pool.py` | `test_skill_capability_gate_*` (5), `test_skill_gated_disciplines_*` (3); `test_skill_gates_*` (3) |
| Suite green | full suite | `pytest tests/ etl/tests/ -q` → 2351 passed / 30 skipped |

### 5.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. this handoff · 5. `./scripts/verify-handoff.sh`. **#336 is shipped + merged.** The skill-capability gate is live in code but **data-gated** on `layer0.skill_capability_toggles` being populated on Neon (owed deploy, §4 item 2) — until applied, the 2C flags never fire and the gate is inert (fail-safe in the wrong direction: nothing gated). Next focus is go-live blockers **#539 / #540**.

## 6. Stop-and-ask status

The one genuine design fork (HITL-flag vs hard-exclude vs substitute) was put to Andy via `AskUserQuestion` before implementing — he chose **automatic strength substitution + coach note**, which reshaped the design from a Layer 2A inclusion gate to a Layer 4 session-level substitution gate. No new LLM prompt body was authored (the directive is appended to the existing per-phase user prompt); no schema/cross-layer-contract change (reads the existing 2C flag); the new validator rule is additive.

## 7. Summary

Closed #336: the skill-capability signal now **enforces substitution** instead of being an inert advisory. A new `blocker` validator rule (`_rule_skill_capability_gate`) reads the Layer 2C `requires_skill_capability` flags — finally consuming the orphaned flag from #298 — and rejects any skill-specific (`kind=='cardio'`) session tagged to a discipline whose required skill toggle is OFF; strength substitutions pass. The per-phase synthesizer prompt is given an explicit substitution directive plus an inline session-grid annotation so it swaps in grip/upper-body strength with a coach note ("prescribing strength until you're cleared on `<skill>`"). Andy chose substitution over HITL/exclude; the key data finding (D-012's exercises are already AR strength, so the prescribed climbing was discipline-level sport sessions) placed the fix at the session level. Suite 2351 green; CI green; squash-merged as `94ec454`. **One owed deploy:** confirm `layer0.skill_capability_toggles` is populated on Neon — the gate is data-driven off it.
