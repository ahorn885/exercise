# Plan Management Spec — v1

Owner: query/derivation subsystem. No LLM involvement. Closes Layer 2E open
items **2E-2** (`HeatAcclimState` contract), **2E-3** (`expected_race_temp_c`
derivation), **2E-4** (`current_phase` source of truth), and backlog **D-53**
(heat-acclim derivation spec). Unblocks GitHub #210 sub-issues #220 (heat
de-stub) and #221 (heat-acclim derivation).

This spec follows the 14-section layer-spec depth standard (`Layer2C_Spec.md`),
**adapted**: Plan Management is not a single query node returning one typed
payload — it is a read-time **derivation subsystem** that assembles the
`PlanManagementState` contract Layer 2E imports, plus two adjacent
plan-lifecycle surfaces (weight-staleness, adherence-drop) that drive
invalidation and Layer 4. §3 therefore documents the contract + per-surface
derivation rather than one function signature.

---

## 1. Purpose

Layer 2E (`Layer2E_Spec.md` §3) imports a `PlanManagementState` value it does
not own and cannot compute itself — it depends on plan-calendar position
(`current_phase`), the athlete's recent heat exposure (`heat_acclim_state`),
and the expected temperature at each target event (`expected_race_temp_c`).
Until this spec, `PlanManagementState` and `HeatAcclimState` were **named but
undefined** (`Layer2E_Spec.md` §3 note, §5.8 "Plan Management spec, not yet
written"), forcing 2E's §5.8 heat-acclim overlay to ship as a stub that
surfaces `temp_signal='unknown'` + `race_temp_unknown` for every event.

Plan Management is the subsystem that:

1. Knows where the athlete is in their generated plan (which periodization
   phase is active today).
2. Derives the athlete's heat-acclimation state at read time from logged
   training conditions (per `Athlete_Data_Integration_Spec` §2.6 — derived,
   not stored).
3. Resolves an expected race temperature per target event from the event
   locale's coordinates and date.
4. Tracks two plan-lifecycle advisories — stale body weight and adherence
   drop — that trigger downstream re-runs.

This spec defines the contract those consumers read and the read-time rules
that produce each value.

## 2. What Plan Management does NOT do

- **It does not store heat-acclim state.** Per `Athlete_Data_Integration_Spec`
  §2.6, heat-acclim state is derived at read time. No new column, no new
  table. (§5.2 below.)
- **It does not own periodization shape.** Layer 3B
  (`Layer3_3B_Spec.md`) owns `periodization_shape`. Plan Management reads it
  and the plan start date to locate today's phase (§5.1). It does not decide
  the shape.
- **It does not own the adherence-drop threshold.** Onboarding
  `Athlete_Onboarding_Data_Spec` "Plan Management 2 / §M.3" owns the rule
  (4 consecutive flagged sessions). Plan Management exposes the resulting
  state; it does not redefine the threshold (§5.5).
- **It does not gate plan-gen.** Plan Management surfaces are inputs and
  advisories. HITL gating lives in Layer 3.5 / per-node specs. The only
  Plan-Management-driven gate-adjacent behavior is invalidation (§6).
- **It is not an LLM node.** Deterministic given inputs + a weather fetch.
  One external call (climate/forecast) per event with coordinates; everything
  else is indexed reads + pure-Python math.

## 3. The `PlanManagementState` contract

This is the typed value Layer 2E imports verbatim (`Layer2E_Spec.md` §3). Its
three fields are the cross-layer surface; field names and types are **locked**
by 2E's signature and must not drift.

```python
@dataclass
class PlanManagementState:
    current_phase: str                              # 'Base' | 'Build' | 'Peak' | 'Taper'  — §5.1
    heat_acclim_state: HeatAcclimState              # §5.2
    expected_race_temp_c: dict[str, float | None]   # event_id → expected temp °C; None = unresolved  — §5.3


@dataclass
class HeatAcclimState:
    level: str                  # 'low' | 'moderate' | 'high'                 — §5.2.3
    days_at_temp_last_30: int   # count of training days >25 °C in last 30 days — §5.2.2
    last_assessment: date       # read-time derivation date                    — §5.2
```

Both shapes match the forward-declarations in `Layer2E_Spec.md` §3 and §5.8
byte-for-byte. If a future consumer needs additional fields, **extend** the
struct (2E ignores extras); do not rename or retype the three above.

### 3.1 Adjacent Plan Management surfaces (not in the 2E struct)

Two plan-lifecycle signals are owned by Plan Management but are **not** carried
in the `PlanManagementState` struct 2E imports — they are delivered to their
own consumers (the invalidation engine and Layer 4), so packing them into the
2E struct would be dead weight 2E never reads. They are specified here because
the epic (#210) and `Control_Spec` §4 name them as Plan Management surfaces.

```python
@dataclass
class WeightStalenessAdvisory:
    is_stale: bool              # body_weight_kg older than the staleness window  — §5.4
    last_confirmed: date | None
    age_days: int | None

@dataclass
class AdherenceDropState:
    active: bool                # per onboarding §M.3 (4 consecutive flagged sessions) — §5.5
    branch: str | None          # 'Sick' | 'Stressed' | 'Bored' | 'Busy' | None
    muted_until: date | None    # 14-day mute window after the prompt
```

### 3.2 Per-field consumers

| Surface | Consumed by | Effect |
|---|---|---|
| `current_phase` | 2E §5.2 (activity multiplier), §5.3 (macro phase scaling) | Calorie + macro targets per phase |
| `heat_acclim_state` | 2E §5.8 `_hot_event_adjustment` | Heat-acclim-gap flags, fluid/Na bias on hot events |
| `expected_race_temp_c` | 2E §5.8 `heat_acclim_overlay` | Per-event temp band → fluid/Na modifiers |
| `WeightStalenessAdvisory` | Invalidation engine → 2E (BMR re-run on confirm) | Prompt re-confirm; re-run 2E when weight updated |
| `AdherenceDropState` | Layer 4 (load caps / context branch) | Plan adaptation; not read by 2E |

## 4. Inputs

Plan Management derives the contract from data it reads; it has no athlete-form
inputs of its own.

| Input | Source | Used for |
|---|---|---|
| `periodization_shape` | Layer 3B output (`Layer3_3B_Spec.md`) | `current_phase` (§5.1) |
| Plan start date | Plan record (`plan_versions` / plan calendar anchor) | `current_phase` (§5.1) |
| `today` | Clock (injectable for determinism — §8) | `current_phase`, `heat_acclim_state.last_assessment` |
| `conditions_log` rows (last 30 days) | `public.conditions_log.temp_f`, `.date` | `heat_acclim_state` (§5.2) |
| Target events | Layer 1 §H.2 (`event_id`, `event_date`, locale FK) | `expected_race_temp_c` (§5.3) |
| Event locale coordinates | `race_events.event_locale_lat`, `.event_locale_lng` | `expected_race_temp_c` (§5.3) |
| Climate normals / forecast | `weather_client.get_expected_conditions()` (Open-Meteo) + forecast endpoint (§5.3) | `expected_race_temp_c` (§5.3) |
| Last weight-confirm timestamp | §A `body_weight_kg` source/updated_at | `WeightStalenessAdvisory` (§5.4) |
| Flagged-session history | Onboarding §M.3 adherence tracking | `AdherenceDropState` (§5.5) |

## 5. Derivation algorithm

### 5.1 `current_phase` — from 3B shape + plan start

**Decision (Andy 2026-06-29): derive from Layer 3B `periodization_shape` +
plan start date + week index, NOT from a Layer 4 persisted calendar.** This
keeps Plan Management's phase reading independent of Layer 4's plan-gen
correction loop, which is the canonical periodization source of truth (3B
owns the shape; 4 only renders sessions into it).

```python
def derive_current_phase(periodization_shape, plan_start: date, today: date) -> str:
    # periodization_shape is an ordered list of phase blocks, each with a
    # phase label ∈ {Base, Build, Peak, Taper} and a week span (Layer3_3B_Spec).
    if today < plan_start:
        return periodization_shape[0].phase          # pre-plan → first block
    week_index = (today - plan_start).days // 7
    cursor = 0
    for block in periodization_shape:
        if week_index < cursor + block.week_count:
            return block.phase
        cursor += block.week_count
    return periodization_shape[-1].phase             # past plan end → last block (Taper)
```

Edge behavior: before plan start clamps to the first block; after the last
block clamps to the last (a completed/over-running plan reads as `Taper`,
the conservative low-volume default for nutrition scaling).

**Accepted tradeoff / best argument against (gut check, §14):** if Layer 4's
capped correction loop reshapes blocks (e.g. compresses Build under a fatigue
condition, `Layer3_3B_Spec` §6.1), the 3B-shape-derived phase can diverge from
the sessions Layer 4 actually rendered. v1 accepts this — 3B shape is the
periodization contract and reshaping is rare and bounded. If first-cohort data
shows material divergence, reconcile by having Layer 4 persist the realized
per-week phase label and reading that instead (tracked §12 PM-1).

### 5.2 `heat_acclim_state` — derived from logged conditions (closes #221)

Per `Athlete_Data_Integration_Spec` §2.6: **derived at read time, never
stored.** Source is the athlete's logged training conditions.

#### 5.2.1 Source and unit conversion

`public.conditions_log` stores temperature in **°F** (`temp_f`, REAL). The
contract is in °C. The acclimation threshold is **25 °C = 77 °F** (the
`Layer2E_Spec` §3 definition: "training days at >25 °C"). Compare in the native
stored unit to avoid rounding drift: a row counts when `temp_f > 77.0`.

```sql
-- Distinct training days in the last 30 with a hot logged condition.
SELECT COUNT(DISTINCT date) AS days_at_temp
  FROM conditions_log
 WHERE user_id = :uid
   AND date >= :today - INTERVAL '30 days'
   AND temp_f > 77.0;        -- 25 °C
```

#### 5.2.2 `days_at_temp_last_30`

The `COUNT(DISTINCT date)` above. Distinct *days*, not rows — two logged
sessions on one hot day count once, matching the physiological model (heat
exposure is a per-day stimulus).

#### 5.2.3 `level` banding

Banding is grounded in the acclimatization timeline 2E already encodes —
"10–14 days minimum for full acclimatization" (`Layer2E_Spec.md` §5.8
`_hot_event_adjustment`):

| `days_at_temp_last_30` | `level` | Rationale |
|---|---|---|
| 0–4 | `low` | Below the threshold where meaningful adaptation begins |
| 5–13 | `moderate` | Partial adaptation; protocol in progress |
| ≥14 | `high` | At/over the 14-day full-acclimatization floor |

`last_assessment = today` (the read-time derivation date).

#### 5.2.4 Sparse / absent data

If the athlete has **fewer than 5 logged condition-days total** in the window
(not just hot ones — i.e. we have almost no signal), return
`level='low', days_at_temp_last_30=<count>` AND have the consumer surface a
`heat_acclim_data_sparse` advisory. Rationale: `low` is the conservative
default (it makes 2E *more* likely to fire the heat-acclim-gap flag, which is
the safe direction for a hot race), but the advisory makes clear this is a
**data gap**, not a confirmed-unacclimatized reading — an athlete who simply
doesn't log conditions is not the same as one demonstrably not training in
heat. No conditions logged at all → `days=0, level='low'` + the advisory.

#### 5.2.5 Future inputs (deferred)

Per Integration Spec §2.6, future signal sources extend §5.2.1 without
changing the contract: integration-sourced ambient temperature (provider
wellness streams), §J locale climate seasonality (an athlete training in a hot
locale who under-logs conditions). v1 uses `conditions_log` only. Tracked §12
PM-2.

### 5.3 `expected_race_temp_c` — per event (closes 2E-3)

**Decision (Andy 2026-06-29): climate normal blended toward live forecast when
the event is inside the forecast horizon.** Far-out events use historical
climate normals; near events blend toward the live forecast.

```python
FORECAST_HORIZON_DAYS = 14   # Open-Meteo forecast reach

def derive_expected_race_temp_c(events, today: date) -> dict[str, float | None]:
    out = {}
    for ev in events:
        lat, lng = ev.event_locale_lat, ev.event_locale_lng
        if lat is None or lng is None:
            out[ev.event_id] = None          # 2E surfaces race_temp_unknown
            continue
        normal = weather_client.get_expected_conditions(lat, lng, ev.event_date, today=today)
        normal_high = normal.temp_max_c if normal else None
        days_out = (ev.event_date - today).days
        if 0 <= days_out <= FORECAST_HORIZON_DAYS:
            forecast_high = weather_client.get_forecast_high(lat, lng, ev.event_date)  # §5.3.2
            out[ev.event_id] = _blend(normal_high, forecast_high, days_out)
        else:
            out[ev.event_id] = normal_high
    return out
```

#### 5.3.1 Which temperature

`expected_race_temp_c` is the **expected daytime high** at the locale around
the event date — `ExpectedConditions.temp_max_c` from
`weather_client.get_expected_conditions()`. The race happens during the day;
the daily high is the heat-stress-relevant value, and 2E's §5.8 bands
(`<18 cool`, `<26 temperate`, `<32 warm`, `≥32 hot`) read as daytime-racing
temperatures.

#### 5.3.2 Forecast leg (new client capability)

`weather_client` today exposes only the climate-normals archive path
(`get_expected_conditions`). The forecast leg adds a sibling
`get_forecast_high(lat, lng, target_date)` against Open-Meteo's forecast
endpoint (same client, same `Fetcher` injection pattern), returning the
forecast daily high °C or `None` on any failure. Implementation belongs to the
#220 de-stub PR; this spec pins the contract.

#### 5.3.3 Blend rule

Linear blend on horizon proximity — full forecast weight at the event, full
normal weight at the horizon edge:

```python
def _blend(normal_high, forecast_high, days_out):
    if forecast_high is None: return normal_high          # forecast failed → fall back to normal
    if normal_high is None:   return forecast_high        # no archive sample → trust forecast
    w_forecast = 1.0 - (days_out / FORECAST_HORIZON_DAYS) # 1.0 at race day → 0.0 at horizon edge
    return round(w_forecast * forecast_high + (1 - w_forecast) * normal_high, 1)
```

#### 5.3.4 Unresolved → `None`

`None` when the event locale has no coordinates, or both normal and forecast
fetches fail. Per `Layer2E_Spec.md` §5.8 + §10, 2E then emits
`temp_signal='unknown'` with a `race_temp_unknown` flag and applies no band
modifier. `None` is a first-class value of the contract, not an error.

### 5.4 Weight-staleness advisory

`body_weight_kg` (§A) drives BMR (`Layer2E_Spec.md` §5.2). A stale weight
silently miscalibrates every calorie/macro target. Plan Management flags it.

- **Window: 60 days.** An endurance training block runs weeks-to-months and
  body weight drifts across it; 60 days balances calibration accuracy against
  prompt fatigue. (Numeric tuning — adjust on cohort feedback, not a contract
  change.)
- `is_stale = (today - last_confirmed).days > 60`. `last_confirmed` is the §A
  weight source/updated timestamp.
- **Advisory, not a gate.** When stale, surface `weight_stale`; the athlete is
  prompted to re-confirm. On confirm/update, `Control_Spec` §4 already wires
  the §A-weight change to a 2E re-run (BMR + macros). No plan-gen block.
- No `last_confirmed` (never set) → `is_stale=True, age_days=None`.

### 5.5 Adherence-drop state (references onboarding §M.3)

The threshold is **owned by onboarding** (`Athlete_Onboarding_Data_Spec`
"Plan Management 2 / §M.3": 4 consecutive flagged sessions → adherence-drop
prompt). Plan Management does **not** redefine it — it exposes the resulting
state for Layer 4.

- `active = True` once §M.3's 4-consecutive-flagged-sessions condition is met.
- `branch ∈ {Sick, Stressed, Bored, Busy}` per the §M.3 prompt response;
  drives Layer 4's context adaptation.
- `muted_until = prompt_date + 14 days` (the §M.3 mute window). While muted,
  the trigger does not re-fire. (The branch-specific mute durations floated in
  `V2_Spec_Prep_Handoff` open item #10 — Sick 5–10d, others 14d — are deferred;
  v1 uses the flat 14-day mute §M.3 specifies. Tracked §12 PM-3.)
- Not consumed by 2E. Specified here only because it is a Plan Management
  surface named by the epic and `Control_Spec` §4.

## 6. Invalidation & partial-update consistency

`Control_Spec` §4 already declares the Plan-Management-state → re-run triggers.
This spec must stay consistent with them; it does not introduce new ones.

| Plan Management surface change | Re-runs | Source of truth |
|---|---|---|
| `current_phase` | 2E (activity multiplier, macro phase scaling) | `Control_Spec` §4 |
| `heat_acclim_state` per event | 2E (race-day fueling fluid + salt) | `Control_Spec` §4 |
| `expected_race_temp_c` per event | 2E (heat-acclim event adjustments) | `Control_Spec` §4 |
| Weight-staleness → athlete confirms new weight | 2E (BMR + macros) | `Control_Spec` §4 (§A weight row) |
| Adherence-drop | Layer 4 (load caps / context) | onboarding §M.3 |

`current_phase`, `heat_acclim_state`, and `expected_race_temp_c` are derived at
read time, so they have no stored row to invalidate — a re-run recomputes them
from current inputs. The invalidation rows above fire when the *inputs* change
(plan calendar advances a week; a new hot condition is logged; an event locale
or date changes; weight is re-confirmed).

## 7. Coaching flags / advisories

Plan Management itself emits no coaching flags into a payload (it has no
payload — it returns the contract). The two advisories it raises are delivered
to their consumers, which render them:

| Advisory | Raised when | Consumer rendering |
|---|---|---|
| `heat_acclim_data_sparse` | §5.2.4 — <5 logged condition-days in window | 2E surfaces alongside the heat-acclim overlay so a `low` reading isn't misread as confirmed |
| `weight_stale` | §5.4 — weight older than 60 days | Profile prompt to re-confirm weight |

The heat-acclim *gap* flags (`heat_acclim_gap`, `heat_acclim_in_progress`) are
owned and emitted by 2E §5.8 from `heat_acclim_state`; Plan Management only
supplies the state.

## 8. Caching & determinism

- **Deterministic given (inputs, `today`, weather responses).** `today` is
  injectable (matches `weather_client.get_expected_conditions(today=...)`) so
  tests pin the clock.
- **Weather is the only nondeterministic dependency.** `get_expected_conditions`
  and `get_forecast_high` take an injectable `Fetcher`; tests pass a stub
  fetcher for byte-stable results. Live fetches vary day-to-day by design
  (forecast updates) — this is correct, not a determinism bug, and is why
  `expected_race_temp_c` is recomputed on read rather than pinned to
  `etl_version_set`.
- **No stored derived state** (§2). Nothing to cache-key or invalidate beyond
  the §6 input-change triggers.

## 9. Edge cases

| Case | Behavior |
|---|---|
| `today` before plan start | `current_phase` = first block (§5.1). |
| `today` past plan end | `current_phase` = last block (Taper). |
| `periodization_shape` empty/missing | Caller has no plan; Plan Management is not invoked. If invoked, raise — a phase with no plan is a contract violation, not a default. |
| No `conditions_log` rows | `heat_acclim_state = {low, 0, today}` + `heat_acclim_data_sparse` (§5.2.4). |
| <5 logged condition-days | Same as above — `low` + sparse advisory. |
| Hot day logged with `temp_f` NULL | Row excluded from the count (`temp_f > 77.0` is NULL-safe-false). |
| Event with no locale coords | `expected_race_temp_c[event_id] = None` → 2E `race_temp_unknown` (§5.3.4). |
| Event in the past (`event_date < today`) | `days_out < 0` → normal-only leg (§5.3); 2E §10 already skips past-event race-day fueling. |
| Forecast fetch fails inside horizon | Blend falls back to climate normal (§5.3.3). |
| Both normal + forecast fail | `None` → `race_temp_unknown`. |
| Weight never confirmed | `WeightStalenessAdvisory{is_stale=True, last_confirmed=None, age_days=None}` (§5.4). |
| Multiple events, mixed coord availability | Per-event resolution; some `float`, some `None` in the dict. No cross-event reconciliation. |

## 10. Performance budget

Per `Control_Spec` §6 / 2E precedent (<500 ms for a 2E call, of which Plan
Management is an input):

- **§5.1 phase derivation:** pure-Python walk over a handful of blocks. <1 ms.
- **§5.2 heat-acclim:** 1 indexed `COUNT(DISTINCT date)` on `conditions_log`
  (user-scoped, 30-day window). ~5 ms.
- **§5.3 expected race temp:** the cost center — **1–2 external HTTP calls per
  event with coordinates** (climate archive always; forecast when ≤14 days
  out). `get_expected_conditions` issues `_NORMALS_YEARS` archive requests
  internally. Network-bound, not CPU-bound; budget ~300–800 ms per event under
  live fetch. **Events typically 1–3**, so ~1–2 s worst case for a
  multi-event athlete.
- **§5.4 / §5.5:** trivial reads. <5 ms.

**Implication:** because §5.3 is network-bound and can exceed the per-call 2E
budget, Plan Management's weather resolution should be **computed/refreshed on
the §6 input-change triggers** (event locale/date change, or a periodic
refresh as the event nears the forecast horizon) and the resolved
`expected_race_temp_c` handed to 2E as an already-materialized input — not
fetched synchronously inside every 2E call. The contract value is a plain
`dict[str, float | None]`; how fresh it is, is a Plan Management scheduling
concern. Tracked §12 PM-4 (refresh cadence as events cross the horizon).

## 11. Open items / forward references

| # | Item | Owner | Status |
|---|---|---|---|
| PM-1 | **Phase divergence under Layer 4 reshaping** — §5.1 derives phase from 3B shape; if Layer 4's correction loop reshapes blocks, persisted-realized phase may diverge. Reconcile by reading a Layer 4 per-week phase label if cohort data shows material drift. | Layer 4 / Plan Management | Deferred — accepted tradeoff (§5.1 gut check) |
| PM-2 | **Heat-acclim future signal sources** — integration ambient temp + §J locale climate seasonality extend §5.2.1 without contract change. | Plan Management | Deferred (Integration Spec §2.6) |
| PM-3 | **Branch-specific adherence-drop mute durations** — §M.3 flat 14-day mute; `V2_Spec_Prep` open item #10 floats Sick 5–10d. | Onboarding §M | Deferred until adherence data exists |
| PM-4 | **`expected_race_temp_c` refresh cadence** — when to re-resolve as an event crosses the 14-day forecast horizon (§10). | Plan Management | Deferred — scheduling, not contract |
| PM-5 | **`get_forecast_high` client method** — forecast leg of §5.3.2 not yet in `weather_client.py`; lands with the #220 de-stub PR. | `weather_client` | Pending #220 |

## 12. Implementation handoff (for #220 / #221)

- **#221 (heat-acclim derivation):** implement §5.1 + §5.2 against
  `conditions_log`; emit `HeatAcclimState` + the `heat_acclim_data_sparse`
  advisory. No new schema.
- **#220 (heat de-stub):** add `weather_client.get_forecast_high()` (§5.3.2),
  implement §5.3 `derive_expected_race_temp_c`, and replace
  `_stub_heat_acclim_adjustments()` (`layer2e/builder.py`) with a real
  `heat_acclim_overlay` fed by this contract. The 2E §5.8 algorithm already
  exists in spec form (`Layer2E_Spec.md` §5.8) — wire it to the now-defined
  contract.
- **Logging (Rule #15):** §5.1 log the resolved phase + (plan_start, week_index);
  §5.2 log days_at_temp + chosen level; §5.3 log per-event chosen temp +
  source (normal / forecast-blend / unresolved) + days_out. Every silent
  fallback (sparse data, forecast-failed blend, None) must print its branch.

## 13. Test scenarios

### 13.1 Andy at PGE 2026 — temperate event, sparse heat logs
- Plan start 2026-04-01, 15-week plan, `today` mid-Build → `current_phase=Build`.
- `conditions_log`: MN spring, few days >77 °F → `days_at_temp_last_30` low,
  `level='low'` (+ `heat_acclim_data_sparse` if <5 logged days).
- PGE locale coords present, event 2026-07-17, `today` >14 days out → climate
  normal high for Nerstrand MN mid-July ≈ 25–28 °C → `expected_race_temp_c`
  ≈ that value; 2E reads `temperate`/`warm` band. Matches `Layer2E_Spec` §13.1's
  assumed `{PGE: 25.0}`.
- Weight last confirmed within 60 days → `is_stale=False`.

### 13.2 Hot marathon inside forecast horizon
- Event 10 days out, locale coords present. Forecast high 33 °C, climate
  normal 29 °C → blend `w_forecast = 1 - 10/14 ≈ 0.286` →
  `≈ 0.286·33 + 0.714·29 ≈ 30.1 °C`. 2E reads `warm`. Low acclim + <14 days →
  2E fires `heat_acclim_gap`.

### 13.3 Event with no locale coordinates
- `event_locale_lat/lng` NULL → `expected_race_temp_c[event_id] = None` → 2E
  `temp_signal='unknown'` + `race_temp_unknown`, no band modifier. No error.

### 13.4 No conditions logged
- Empty `conditions_log` → `heat_acclim_state = {low, 0, today}` +
  `heat_acclim_data_sparse`. Phase + race temp still resolve independently.

### 13.5 Plan over-run
- `today` past plan end → `current_phase=Taper` (last block clamp, §5.1).

### 13.6 Stale weight
- `body_weight_kg` last confirmed 75 days ago → `weight_stale` advisory;
  re-confirm triggers 2E BMR re-run (`Control_Spec` §4).

## 14. Gut check

**What this spec gets right:** it pins exactly the three-field contract 2E
already imports (no cross-layer churn), formalizes the "derived, not stored"
rule the Integration Spec §2.6 already committed to, and reuses the
`weather_client` + `conditions_log` + `race_events` surfaces that already
exist — so #220/#221 are wiring jobs, not green-field design.

**Risks / best argument against:**
- **§5.1 phase divergence (PM-1)** is the real soft spot — deriving phase from
  3B shape rather than Layer 4's realized calendar can drift if the correction
  loop reshapes blocks. Accepted for v1 (3B is the periodization contract,
  reshaping is bounded), but it's the first thing to revisit on cohort data.
- **§5.3 is network-bound** and can blow the per-call 2E budget if fetched
  synchronously — §10/PM-4 push resolution onto the input-change triggers
  instead, but that introduces a freshness/scheduling concern this spec only
  sketches.
- **Heat-acclim banding (§5.2.3) and the 60-day weight window (§5.4)** are
  evidence-anchored but ultimately tunable judgment calls; they should move on
  first-cohort feedback, and the spec marks them as tuning, not contract.
- **§5.2.4 sparse-data → `low`** biases toward firing the heat-acclim-gap flag.
  That's the safe direction for a hot race, but a non-logging athlete who
  trains in heat will be told they're unacclimatized. The `heat_acclim_data_sparse`
  advisory is the mitigation; whether that's enough is a UX call.
