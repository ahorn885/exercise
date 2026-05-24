"""Repository helpers for the athlete-side skill-capability toggle
state and the canonical Layer 0 vocab.

Wires the capture surface — `/onboarding/skills` + `/profile?tab=skills`
— to the Bucket C sub-item (l) tables shipped 2026-05-24:

- `layer0.skill_capability_toggles` — canonical vocab (toggle_name,
  display_label, description, gated_terrain_ids, gated_discipline_ids).
- `athlete_skill_toggles` — per-athlete state (user_id, toggle_name,
  enabled BOOLEAN DEFAULT FALSE).

Layer 1's existing `_load_skill_toggle_states` remains the runtime
read path; this module exposes parallel public helpers for the UI.
"""

from layer4.cache import Layer4Cache
from layer4.cache_invalidation import evict_on_layer_change
from layer4.cache_postgres import PostgresCacheBackend


def load_active_skill_capability_toggle_vocab(db):
    """Return active toggle vocab rows for UI rendering.

    Filters on `superseded_at IS NULL` so transient overlap during a
    0C-version bump surfaces whatever is currently live. Ordered by
    `toggle_name` for stable checkbox layout across renders.

    Returns a list of dicts with `toggle_name`, `display_label`,
    `description`. Empty list when the populate script has not yet run.
    """
    rows = db.execute(
        'SELECT toggle_name, display_label, description '
        'FROM layer0.skill_capability_toggles '
        'WHERE superseded_at IS NULL '
        'ORDER BY toggle_name'
    ).fetchall()
    return [dict(r) for r in rows]


def get_athlete_skill_toggles(db, user_id: int) -> dict:
    """Return the athlete's per-toggle enabled state.

    Empty dict on athletes with no rows. Mirrors
    `layer1.builder._load_skill_toggle_states` semantics but exposed as
    a public helper for the capture-surface route handlers.
    """
    rows = db.execute(
        'SELECT toggle_name, enabled FROM athlete_skill_toggles '
        'WHERE user_id = ?',
        (user_id,),
    ).fetchall()
    return {r['toggle_name']: bool(r['enabled']) for r in rows}


def upsert_athlete_skill_toggles(db, user_id: int, states: dict) -> None:
    """UPSERT one row per (user_id, toggle_name).

    `states` keys must be toggle_name strings from the canonical vocab;
    values are booleans. Caller is responsible for filtering unknown
    toggle names before invoking — this helper does not validate vocab
    membership. Caller commits.

    Idempotent re-runs are safe via the UNIQUE (user_id, toggle_name)
    constraint shipped in `init_db._PG_MIGRATIONS`.
    """
    for toggle_name, enabled in states.items():
        db.execute(
            'INSERT INTO athlete_skill_toggles '
            '  (user_id, toggle_name, enabled, created_at, updated_at) '
            'VALUES (?, ?, ?, NOW(), NOW()) '
            'ON CONFLICT (user_id, toggle_name) DO UPDATE SET '
            '  enabled = EXCLUDED.enabled, updated_at = NOW()',
            (user_id, toggle_name, bool(enabled)),
        )


def evict_layer1_on_skill_toggle_change(db, user_id: int) -> None:
    """Fire `evict_on_layer_change(cache, uid, 'layer1')` after a save.

    Skill state lives in `Layer1Lifestyle.skill_toggle_states` so saves
    invalidate every Layer 4 entry point + both Layer 3 wrappers per
    the Layer 1 eviction policy at `layer4/cache_invalidation.py`.

    Mirrors `routes.locales._evict_layer2b_on_terrain_change`: builds a
    transient `Layer4Cache` per request (Vercel stateless model).
    """
    cache = Layer4Cache(PostgresCacheBackend(lambda: db))
    evict_on_layer_change(cache, user_id, 'layer1')


def parse_skill_form(form, vocab) -> dict:
    """Coerce a POST form into a `{toggle_name: bool}` dict.

    Checkboxes use `skill__<toggle_name>` as the input name; presence
    means True, absence means False. Only toggle names in `vocab` are
    returned (defends against malformed POSTs that include unknown
    keys). Returns ALL vocab toggles so explicit-False rows persist
    instead of being collapsed to absent — keeps the
    "athlete deliberately set OFF" signal distinct from "athlete never
    saw this toggle" at the boundary, even though Layer 2B/2C treat
    them identically.
    """
    states = {}
    for entry in vocab:
        key = f"skill__{entry['toggle_name']}"
        states[entry['toggle_name']] = bool(form.get(key))
    return states
