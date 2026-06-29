import json
import re
import uuid

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session)

import locations
import mapbox_client
from chain_registry import GYM_CHAINS, detect_chain
from database import get_db
from layer4.cache import Layer4Cache
from layer4.cache_invalidation import evict_on_layer_change
from layer4.cache_postgres import PostgresCacheBackend
from routes.auth import current_user_id
from athlete_crafts_repo import load_craft_catalog
from athlete_craft_locale_repo import (
    CraftLocaleError,
    evict_plan_caches_on_craft_locale_change,
    load_craft_locales,
    replace_craft_locale,
)

bp = Blueprint('locales', __name__)

# When the locale flow is entered from a host step (e.g. onboarding Step 4) the
# caller passes `?return_to=<local-path>`; we stash it so the terminal "saved a
# location" redirect bounces back there instead of dead-ending on /locales.
# Mirrors the OAuth return_to convention in routes/coros.py (same safety check).
_LOCALE_RETURN_TO = 'locale_return_to'


def _stash_return_to():
    """Persist a safe, local `?return_to` for the duration of the locale flow."""
    rt = request.args.get('return_to')
    if rt and rt.startswith('/') and not rt.startswith('//'):
        session[_LOCALE_RETURN_TO] = rt


def _locale_flow_redirect():
    """Terminal redirect after saving a locale: bounce back to the stashed
    host-step path (consumed once) or fall back to the locale list."""
    target = session.pop(_LOCALE_RETURN_TO, None)
    if target and target.startswith('/') and not target.startswith('//'):
        return redirect(target)
    return redirect(url_for('locales.list_profiles'))

# Locations Consolidation (Track 1, completed WS-B 2026-06-14) — the legacy
# hardcoded home/hotel/partner/airport enum is fully retired. Locales are now
# purely athlete-created (`locale_profiles` + `gym_profiles` + overrides); home
# is the `locale_profiles.preferred` flag (one per athlete, set by `_ensure_home`
# on first build); equipment is the layer0 canonical-name vocabulary. There are
# no force-rendered default slots.


def _layer0_equipment(db):
    """Return `(categories, names)` from `layer0.equipment_items` — the
    authoritative equipment vocabulary (Track 1, decision 8). `categories` is
    `[(equipment_category, [(canonical_name, canonical_name), ...]), ...]`
    shaped to match the template's `(category, [(value, label)])` loop (value
    == label == canonical name); `names` is the flat validation set. Active
    rows only (superseded_at IS NULL)."""
    rows = db.execute(
        'SELECT canonical_name, equipment_category FROM layer0.equipment_items '
        'WHERE superseded_at IS NULL '
        'ORDER BY equipment_category, canonical_name'
    ).fetchall()
    categories: list = []
    names: set = set()
    by_cat: dict = {}
    for r in rows:
        name = r['canonical_name']
        cat = r['equipment_category'] or 'Other'
        names.add(name)
        by_cat.setdefault(cat, []).append((name, name))
    for cat in sorted(by_cat):
        categories.append((cat, by_cat[cat]))
    return categories, names



# Phase 5.1 form-refresh C — canonical TRN-xxx slug pattern.
# Route-local duplicate of `routes/race_events.py:_TRN_PATTERN` +
# `routes/onboarding.py:_TRN_PATTERN`; mirrors the form-refresh A/B v1
# duplicate-with-cross-ref strategy. Drift-mitigation: tests on all three
# call sites exercise the same edge cases. Extract to a shared module if a
# fourth call site appears.
_TRN_PATTERN = re.compile(r"^TRN-\d{3}$")


def _terrain_choices(db) -> list[dict]:
    """Return `{id, label, description}` dicts for every active
    `layer0.terrain_types` row.

    Used by the locale-edit template to populate the terrain checkbox grid.
    `id` is the canonical TRN-xxx slug; `label` is the `canonical_name`;
    `description` is the row `notes` (rendered as a hover tooltip so opaque
    labels like "Technical Rock" are self-explanatory — issue #444). ORDER BY
    terrain_id for stable rendering; ~16 rows so no caching. Mirrors
    `routes/race_events.py:_terrain_choices` +
    `routes/onboarding.py:_terrain_choices`, EXCEPT this picker is for
    training venues, so it is intentionally NOT race-eligibility filtered —
    all terrains (incl. climbing gym / pump track / indoor gym) belong here.
    """
    # D-73 Phase 5.2 Bucket E.(a) — defensive `terrain_id IS NOT NULL`
    # filter. See `routes/race_events.py:_terrain_choices` for rationale.
    cur = db.execute(
        'SELECT terrain_id, canonical_name, notes FROM layer0.terrain_types '
        'WHERE superseded_at IS NULL AND terrain_id IS NOT NULL '
        'ORDER BY terrain_id'
    )
    return [
        {'id': r['terrain_id'], 'label': r['canonical_name'],
         'description': r['notes']}
        for r in cur.fetchall()
    ]


def _parse_locale_terrain(form) -> list[str]:
    """Parse the multi-checkbox `locale_terrain_ids` form field into a
    sorted list of canonical TRN-xxx ids.

    Empty / malformed / non-matching entries are silently dropped — the
    template only renders valid TRN-xxx choices so any drift would be a
    crafted POST. Output is sorted for deterministic storage + diff
    detection.
    """
    raw = form.getlist('locale_terrain_ids')
    seen: set[str] = set()
    for value in raw:
        v = (value or '').strip()
        if v and _TRN_PATTERN.match(v) and v not in seen:
            seen.add(v)
    return sorted(seen)


def _hydrate_locale_terrain_ids(profile_row) -> list[str]:
    """Read the `locale_terrain_ids` column off a `locale_profiles` row,
    tolerating the migration-vs-pre-migration row shape.

    Returns `[]` when the column is absent (SQLite dev path that hasn't
    seen the Form-refresh C migration) OR NULL OR empty array. Psycopg2
    returns Postgres TEXT[] as a Python list; SQLite returns it as a
    string or None.
    """
    if profile_row is None or not _row_has(profile_row, 'locale_terrain_ids'):
        return []
    raw = profile_row['locale_terrain_ids']
    if raw is None:
        return []
    if isinstance(raw, list):
        return [v for v in raw if isinstance(v, str) and _TRN_PATTERN.match(v)]
    if isinstance(raw, str):
        # SQLite shim path — stored as JSON-ish text. Try JSON; fall back
        # to the literal-empty-array case.
        s = raw.strip()
        if not s or s in ('{}', '[]'):
            return []
        try:
            parsed = json.loads(s)
        except (ValueError, TypeError):
            return []
        if isinstance(parsed, list):
            return [
                v for v in parsed
                if isinstance(v, str) and _TRN_PATTERN.match(v)
            ]
    return []


def _evict_layer2b_on_terrain_change(db, user_id: int) -> None:
    """Fire `evict_on_layer_change(cache, uid, 'layer2b')` so the next
    plan_create / plan_refresh / race_week_brief invocation re-derives
    Layer 2B with the new locale_terrain_ids set.

    Per Phase 5.1 form-refresh C D10: evicts on edits to ANY locale (not
    just home) for forward-compatibility with cluster-union; over-eviction
    cost is one extra cache miss per non-home-locale save. Builds a
    transient `Layer4Cache` per request (Vercel stateless model;
    `race_events_invalidation._build_default_cache` precedent).
    """
    cache = Layer4Cache(PostgresCacheBackend(lambda: db))
    evict_on_layer_change(cache, user_id, 'layer2b')


def _evict_layer2c_on_equipment_change(db, user_id: int) -> None:
    """Fire `evict_on_layer_change(cache, uid, 'layer2c')` so the next
    plan_create / plan_refresh / single_session_synthesize / race_week_brief
    invocation re-derives Layer 2C with the new equipment pool.

    Mirrors `_evict_layer2b_on_terrain_change` precedent — fires on edits
    to ANY locale (not just home). Layer 2C policy is `_ALL_ENTRY_POINTS`
    (broader than 2B's `_NON_SINGLE_SESSION`) because equipment changes
    also invalidate on-demand single-session synthesis. Caller gates on
    actual change so no-op saves don't burn the cache.
    """
    cache = Layer4Cache(PostgresCacheBackend(lambda: db))
    evict_on_layer_change(cache, user_id, 'layer2c')

# D-59 §8 — disclosure_id stored in disclosure_acknowledgments. Bumped only
# when the disclosure copy materially changes; athletes re-acknowledge on
# bump.
MAPBOX_DISCLOSURE_ID = 'mapbox_geocoding_consent'
MAPBOX_DISCLOSURE_VERSION = 'v1'

# D-60 §3 — locale category taxonomy. Manual-entry dropdown surfaces the
# whole taxonomy so athletes can pick the right value when bypassing chain
# detection. Every category now uses the unified gym_profiles + overrides
# model (Track 1); residential categories (RESIDENTIAL_CATEGORIES) default
# private. PR18 reclassified outdoor_park as publicly shareable: the privacy
# boundary is residence-vs-public, not gym-vs-non-gym.
MANUAL_CATEGORIES = (
    ('commercial_chain_gym', 'Commercial gym (chain)'),
    ('independent_gym', 'Commercial gym (independent)'),
    ('hotel_gym', 'Hotel gym'),
    ('climbing_gym_chain', 'Climbing gym (chain)'),
    ('climbing_gym_indie', 'Climbing gym (independent)'),
    ('pool_indoor', 'Indoor pool'),
    ('pool_outdoor', 'Outdoor pool'),
    ('home_gym', 'Home (primary residence)'),
    ('outdoor_park', 'Outdoor / trail / park'),
    ('other_residence', 'Other residence (in-laws / friend / AirBnB)'),
)

# Track 1 §6 — residential categories default `gym_profiles.private = TRUE`
# (excluded from crowd-source discovery/dispute/visibility; otherwise identical
# storage + picker). Every other category is shareable by default.
RESIDENTIAL_CATEGORIES = frozenset({'home_gym', 'other_residence'})


def _category_default_private(category) -> bool:
    """The category-derived privacy default (Track 1 §6). Residential
    categories default private; everything else defaults shareable. A
    categoryless locale (legacy enum slug / un-categorized manual entry)
    falls back to the residential default — matching `_create_gym_profile`,
    where `category or 'home_gym'` keeps the NOT-NULL column populated."""
    return (category or 'home_gym') in RESIDENTIAL_CATEGORIES


def _resolve_private(category, sharing_opt_out) -> bool:
    """Effective `gym_profiles.private` for a locale (#446). Residential
    categories are always private; a shareable-category locale becomes
    private when the athlete explicitly opts out of sharing
    (`locale_profiles.sharing_opt_out`) — e.g. a residence that Mapbox
    returned as `commercial_gym`. Residences are never crowd-shareable, so
    the opt-out can only tighten privacy, never loosen a residence."""
    return _category_default_private(category) or bool(sharing_opt_out)


# PR19 Item E — map MANUAL_CATEGORIES → Layer 0 exercise_inventory.where_available
# buckets. The 4-bucket where_available taxonomy is gym-centric (home / hotel /
# partner / airport); the locale-CRUD model lets athletes save arbitrary places
# with richer categories. This map is what /references/exercises uses to decide
# which exercises are relevant for a selected athlete locale. outdoor_park has
# no analog — parks resolve to '' and match no exercises until the park-specific
# tag taxonomy lands (PR18 closing handoff §5.2).
CATEGORY_TO_WHERE_AVAILABLE_BUCKET = {
    'home_gym': 'home',
    'other_residence': 'home',
    'hotel_gym': 'hotel',
    'commercial_chain_gym': 'partner',
    'independent_gym': 'partner',
    'climbing_gym_chain': 'partner',
    'climbing_gym_indie': 'partner',
    'pool_indoor': 'partner',
    'pool_outdoor': 'partner',
    'outdoor_park': '',
}


def athlete_locale_choices(db, uid: int) -> list:
    """Return ordered list of {slug, label, bucket} dicts representing every
    locale the athlete can pick — the athlete-created `locale_profiles` rows
    (legacy enum slots retired, WS-B). `bucket` is the where_available analog
    used by /references filter logic; it comes from
    CATEGORY_TO_WHERE_AVAILABLE_BUCKET (may be '' when no Layer 0 analog).
    """
    rows = db.execute(
        'SELECT locale, locale_name, category FROM locale_profiles '
        'WHERE user_id = ?',
        (uid,),
    ).fetchall()
    by_slug = {r['locale']: r for r in rows}

    choices = []
    for slug in sorted(by_slug):
        row = by_slug[slug]
        label = row['locale_name'] or slug
        bucket = CATEGORY_TO_WHERE_AVAILABLE_BUCKET.get(row['category'] or '', '')
        choices.append({'slug': slug, 'label': label, 'bucket': bucket})
    return choices


def _slugify(name: str) -> str:
    """URL-safe slug for the `locale` PK column. Lowercase, alnum-only,
    underscore separator, truncated to 48 chars. Empty string when input
    has no alnum characters — caller flashes and rejects."""
    s = re.sub(r'[^a-z0-9]+', '_', (name or '').lower()).strip('_')
    return s[:48]


def _unique_slug(db, uid: int, base: str) -> str:
    """Return `base` if (uid, base) is free; otherwise base_2, base_3, …
    until a free slug is found. Caps at 50 attempts (defensive)."""
    if not base:
        return ''
    candidate = base
    suffix = 2
    while suffix < 50:
        existing = db.execute(
            'SELECT 1 FROM locale_profiles WHERE user_id = ? AND locale = ?',
            (uid, candidate),
        ).fetchone()
        if not existing:
            return candidate
        candidate = f'{base[:44]}_{suffix}'
        suffix += 1
    return candidate


def _disclosure_acked(db, uid: int) -> bool:
    """True when the current user has acknowledged the current Mapbox
    disclosure version (D-59 §8). PG-only — disclosure_acknowledgments is
    a PR1 D-58 PG-only table; SQLite dev returns True so local probes
    don't gate on a missing table."""
    row = db.execute(
        '''SELECT 1 FROM disclosure_acknowledgments
           WHERE user_id = ? AND disclosure_id = ? AND version_id = ?
           LIMIT 1''',
        (uid, MAPBOX_DISCLOSURE_ID, MAPBOX_DISCLOSURE_VERSION),
    ).fetchone()
    return row is not None


def _record_disclosure_ack(db, uid: int) -> None:
    """Insert one disclosure_acknowledgments row. Re-ack writes a new row
    per the comment at init_db.py:1842 (MAX(acknowledged_at) is the
    current-state query, not uniqueness)."""
    db.execute(
        '''INSERT INTO disclosure_acknowledgments
           (user_id, disclosure_id, version_id, delivery_method)
           VALUES (?, ?, ?, ?)''',
        (uid, MAPBOX_DISCLOSURE_ID, MAPBOX_DISCLOSURE_VERSION, 'in_app'),
    )
    db.commit()


def _canonical_name(chain_id: str) -> str:
    for entry in GYM_CHAINS:
        if entry['chain_id'] == chain_id:
            return entry['canonical_name']
    return ''


def _row_has(row, col: str) -> bool:
    """True when `col` is in the row's column set. PG returns RealDictRow;
    SQLite returns sqlite3.Row. Both expose `.keys()`. Guards against the
    new D-59/D-60 columns being absent on SQLite (frozen migrations)."""
    if row is None:
        return False
    try:
        return col in row.keys()
    except Exception:
        return False


def _find_gym_profile(db, mapbox_id):
    """Look up the shared gym profile keyed by mapbox_id (D-60 §4.1). Returns
    the row or None. mapbox_id is UNIQUE on gym_profiles.

    Crowd-source filtering reads the explicit `private` flag (#446): a
    private profile is never surfaced to peers here, so another athlete at
    the same address builds their own profile instead of inheriting one its
    creator marked private. The creator still reaches their own private
    profile via the `gym_profile_id` link in `_resolve_shared_profile`."""
    if not mapbox_id:
        return None
    return db.execute(
        'SELECT * FROM gym_profiles WHERE mapbox_id = ? AND COALESCE(private, FALSE) = FALSE',
        (mapbox_id,),
    ).fetchone()


def _shared_equipment_set(profile_row) -> set:
    """Parse gym_profiles.equipment (JSON array of layer0 canonical names) into
    a set. The picker constrains values to the active catalog, so no static
    whitelist filter is applied here (Track 1 — canonical-direct)."""
    if not profile_row or not _row_has(profile_row, 'equipment'):
        return set()
    payload = profile_row['equipment']
    if not payload:
        return set()
    try:
        tags = json.loads(payload)
    except (ValueError, TypeError):
        return set()
    return {t for t in tags if isinstance(t, str)}


def _load_overrides(db, uid: int, locale: str):
    """Return ({add_tags}, {remove_tags}) for the athlete's overrides on
    this locale. Empty sets when the table doesn't exist (SQLite) or no
    rows match."""
    rows = db.execute(
        '''SELECT equipment_tag, action FROM locale_equipment_overrides
           WHERE user_id = ? AND locale = ?''',
        (uid, locale),
    ).fetchall()
    adds = {r['equipment_tag'] for r in rows if r['action'] == 'add'}
    removes = {r['equipment_tag'] for r in rows if r['action'] == 'remove'}
    return adds, removes


def _save_overrides(db, uid: int, locale: str, shared_tags: set,
                    athlete_tags: set, valid_names: set) -> None:
    """Replace this athlete's overrides on this locale with the diff of
    athlete_tags vs. shared_tags. Atomic-per-locale: DELETE-then-INSERT.
    Stored values are layer0 canonical names; `valid_names` is the active
    catalog used to reject crafted POSTs."""
    db.execute(
        'DELETE FROM locale_equipment_overrides WHERE user_id = ? AND locale = ?',
        (uid, locale),
    )
    adds = athlete_tags - shared_tags
    removes = shared_tags - athlete_tags
    for tag in adds:
        if tag in valid_names:
            db.execute(
                '''INSERT INTO locale_equipment_overrides
                   (user_id, locale, equipment_tag, action)
                   VALUES (?, ?, ?, ?)''',
                (uid, locale, tag, 'add'),
            )
    for tag in removes:
        if tag in valid_names:
            db.execute(
                '''INSERT INTO locale_equipment_overrides
                   (user_id, locale, equipment_tag, action)
                   VALUES (?, ?, ?, ?)''',
                (uid, locale, tag, 'remove'),
            )


def _create_gym_profile(db, uid: int, profile_row, equipment_tags: set,
                        valid_names: set, sharing_opt_out: bool = False):
    """First-athlete-at-this-locale flow. Creates a new gym_profiles row with
    `equipment` as a JSON array of layer0 canonical names and returns the new
    id; caller links via locale_profiles.gym_profile_id. Residential
    categories default `private = TRUE` (Track 1 §6); a shareable-category
    locale is private when the athlete opted out of sharing (#446).

    `sharing_opt_out` is passed explicitly by `_edit_locale` from the freshly
    submitted form so the build picks up a same-request toggle; it falls back
    to the (possibly stale) `profile_row.sharing_opt_out` for other callers."""
    equipment_json = json.dumps(sorted(t for t in equipment_tags if t in valid_names))
    display = profile_row['locale_name'] if _row_has(profile_row, 'locale_name') else None
    category = profile_row['category'] if _row_has(profile_row, 'category') else None
    # gym_profiles.category is NOT NULL. A categoryless locale (a legacy enum
    # slug like 'home', or a manual entry the athlete didn't categorize)
    # defaults to a private residential profile.
    category = category or 'home_gym'
    mapbox_id = profile_row['mapbox_id'] if _row_has(profile_row, 'mapbox_id') else None
    opt_out = bool(sharing_opt_out) or bool(
        _row_has(profile_row, 'sharing_opt_out') and profile_row['sharing_opt_out']
    )
    private = _resolve_private(category, opt_out)
    row = db.execute(
        '''INSERT INTO gym_profiles
           (mapbox_id, display_name, category, equipment,
            created_by_user_id, last_confirmed_by, last_confirmed_at,
            contribution_count, private)
           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1, ?)
           RETURNING id''',
        (mapbox_id, display, category, equipment_json, uid, uid, private),
    ).fetchone()
    return row['id'] if row else None


def _link_gym_profile(db, uid: int, locale: str, gym_profile_id: int) -> None:
    db.execute(
        '''UPDATE locale_profiles SET gym_profile_id = ?
           WHERE user_id = ? AND locale = ?''',
        (gym_profile_id, uid, locale),
    )


def _touch_gym_profile_confirmation(db, uid: int, gym_profile_id: int) -> None:
    """Bump last_confirmed_by/at + contribution_count on inherit. Tracks
    D-60 §4.3 inherit signal so subsequent athletes see fresh provenance."""
    db.execute(
        '''UPDATE gym_profiles
           SET last_confirmed_by = ?, last_confirmed_at = CURRENT_TIMESTAMP,
               contribution_count = COALESCE(contribution_count, 0) + 1
           WHERE id = ?''',
        (uid, gym_profile_id),
    )


def _display_address(profile_row) -> str:
    """Pull the human-readable street address out of `place_payload` JSON
    for UI rendering (PR18 item A — athletes need to distinguish two rows
    with the same locale_name). Returns the Mapbox feature's
    `properties.full_address` (preferred), `properties.place_formatted`
    (fallback), or '' when the payload is absent / malformed / lacks both."""
    if not profile_row or not _row_has(profile_row, 'place_payload'):
        return ''
    payload = profile_row['place_payload']
    if not payload:
        return ''
    try:
        feature = json.loads(payload)
    except (ValueError, TypeError):
        return ''
    if not isinstance(feature, dict):
        return ''
    props = feature.get('properties') or {}
    return props.get('full_address') or props.get('place_formatted') or ''


def _set_home(db, uid: int, locale: str) -> None:
    """Atomically make `locale` the athlete's home: clear the previous home's
    `preferred` flag and set this one's, in the same transaction (Track 1 §10 —
    exactly one home, always). The partial unique index
    `locale_profiles_one_home_idx` backstops this in the DB."""
    db.execute(
        'UPDATE locale_profiles SET preferred = FALSE WHERE user_id = ? AND preferred',
        (uid,),
    )
    db.execute(
        'UPDATE locale_profiles SET preferred = TRUE WHERE user_id = ? AND locale = ?',
        (uid, locale),
    )


def _ensure_home(db, uid: int, locale: str) -> None:
    """First-locale-auto-home (Track 1 §10): flag `locale` home iff the athlete
    has no home yet. Home can be moved later but never cleared to none."""
    row = db.execute(
        'SELECT 1 FROM locale_profiles WHERE user_id = ? AND preferred LIMIT 1',
        (uid,),
    ).fetchone()
    if row is None:
        db.execute(
            'UPDATE locale_profiles SET preferred = TRUE WHERE user_id = ? AND locale = ?',
            (uid, locale),
        )


def _existing_locale_by_mapbox_id(db, uid: int, mapbox_id: str, exclude_slug: str | None = None):
    """Return the existing (slug, locale_name) for a row this athlete
    already has pointing at the same Mapbox feature (PR18 item C —
    duplicate detection at create-time). `exclude_slug` lets the upgrade
    path skip the row being upgraded. None when no duplicate exists."""
    if not mapbox_id:
        return None
    if exclude_slug:
        row = db.execute(
            '''SELECT locale, locale_name FROM locale_profiles
               WHERE user_id = ? AND mapbox_id = ? AND locale != ?
               LIMIT 1''',
            (uid, mapbox_id, exclude_slug),
        ).fetchone()
    else:
        row = db.execute(
            '''SELECT locale, locale_name FROM locale_profiles
               WHERE user_id = ? AND mapbox_id = ?
               LIMIT 1''',
            (uid, mapbox_id),
        ).fetchone()
    return row


def build_locales_list_context(db, uid):
    """Build the locales-list render context (cards, equipment tags, home, and
    display addresses) for a user. Shared by the standalone Locations page and
    the profile Locations tab (#619); the request-specific `return_to` is added
    by the caller.

    locale_profiles is parent-scoped; locale_equipment is parent-JOIN scoped via
    locale_profiles. Session 3 makes the locale PK composite (user_id, locale)
    so users can have independent locales — until then, the global PK means a
    user 2 can't claim a locale name user 1 already owns.
    """
    profiles = {
        r['locale']: r for r in db.execute(
            'SELECT * FROM locale_profiles WHERE user_id = ?', (uid,)
        ).fetchall()
    }
    # Display: athlete-created rows in slug order (legacy enum slots retired, WS-B).
    displayed_locales = sorted(profiles.keys())
    # Equipment per locale via the authoritative resolver — layer0 canonical
    # names from gym_profiles + overrides (Track 1; replaces the legacy
    # locale_equipment join). value == label == canonical name.
    tags_by_locale = {}
    for loc in profiles:
        names = sorted(locations.locale_effective_tags(db, uid, loc))
        if names:
            tags_by_locale[loc] = [{'tag': n, 'label': n} for n in names]
    counts = {loc: len(items) for loc, items in tags_by_locale.items()}
    home_locale = next(
        (loc for loc, p in profiles.items()
         if _row_has(p, 'preferred') and p['preferred']),
        None,
    )
    display_addresses = {loc: _display_address(p) for loc, p in profiles.items()}
    return dict(locales=displayed_locales, profiles=profiles,
                home_locale=home_locale, tags_by_locale=tags_by_locale,
                counts=counts, display_addresses=display_addresses)


@bp.route('/locales')
def list_profiles():
    db = get_db()
    uid = current_user_id()
    _stash_return_to()
    return render_template('locales/list.html',
                           return_to=session.get(_LOCALE_RETURN_TO),
                           **build_locales_list_context(db, uid))


@bp.route('/locales/<locale>/edit', methods=['GET', 'POST'])
def edit_profile(locale):
    db = get_db()
    uid = current_user_id()
    # All locales are athlete-created (D-59) and must already exist for this
    # user — the legacy auto-create-on-first-save enum is retired (WS-B); new
    # locales are built through `new_locale` (Mapbox/manual), not the edit screen.
    existing = db.execute(
        'SELECT 1 FROM locale_profiles WHERE user_id = ? AND locale = ?',
        (uid, locale),
    ).fetchone()
    if not existing:
        flash('Unknown location.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    profile = db.execute(
        'SELECT * FROM locale_profiles WHERE locale=? AND user_id=?',
        (locale, uid)
    ).fetchone()
    return _edit_locale(db, uid, locale, profile)


@bp.route('/locales/<locale>/crafts', methods=['POST'])
def save_locale_crafts(locale):
    """WS-H #581 Slice 5 — the (b) craft↔locale surface, relocated here from the
    event-windows page (craft kept at a place is a property of the place). Replace
    the crafts the athlete keeps at this locale (replace-all; save with none
    checked to clear), validate the slugs + locale via the repo, then evict the
    plan caches it feeds. Resolution is unchanged — only the capture point moved."""
    db = get_db()
    uid = current_user_id()
    if not db.execute(
        'SELECT 1 FROM locale_profiles WHERE user_id = ? AND locale = ?',
        (uid, locale),
    ).fetchone():
        flash('Unknown location.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    try:
        replace_craft_locale(db, uid, locale, request.form.getlist('craft_slug'))
    except CraftLocaleError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('locales.edit_profile', locale=locale))
    db.commit()
    evict_plan_caches_on_craft_locale_change(db, uid)
    flash('Craft kept at this location saved.', 'success')
    return redirect(url_for('locales.edit_profile', locale=locale))


def _resolve_shared_profile(db, uid: int, profile):
    """Resolve the gym_profiles row backing a locale, if any: the linked
    `gym_profile_id` first, else a peer at the same `mapbox_id` (another
    athlete may have built it). Returns (shared_row_or_None, gym_profile_id)."""
    gym_profile_id = (
        profile['gym_profile_id']
        if profile is not None and _row_has(profile, 'gym_profile_id')
        else None
    )
    shared = None
    if gym_profile_id:
        shared = db.execute(
            'SELECT * FROM gym_profiles WHERE id = ?', (gym_profile_id,),
        ).fetchone()
    if not shared:
        mapbox_id = (
            profile['mapbox_id']
            if profile is not None and _row_has(profile, 'mapbox_id')
            else None
        )
        shared = _find_gym_profile(db, mapbox_id)
    return shared, gym_profile_id


def _edit_locale(db, uid: int, locale: str, profile):
    """Unified locale equipment editor (Track 1 — replaces the legacy/shared
    split). Every locale uses the gym_profiles + overrides model on the layer0
    canonical-name vocabulary:

      - no backing profile yet  → build a new gym_profiles row from the
        submission (residential categories default private);
      - the athlete's own profile (created_by == uid) → edit its equipment
        directly;
      - a peer/shared profile (created_by != uid) → inherit + write per-athlete
        deltas to locale_equipment_overrides.
    """
    categories, valid_names = _layer0_equipment(db)
    shared, gym_profile_id = _resolve_shared_profile(db, uid, profile)
    shared_tags = _shared_equipment_set(shared)
    owns_shared = bool(
        shared and _row_has(shared, 'created_by_user_id')
        and shared['created_by_user_id'] == uid
    )
    inherit = bool(shared and not owns_shared)
    prior_terrain_ids = _hydrate_locale_terrain_ids(profile)
    prior_effective = locations.locale_effective_tags(db, uid, locale)

    if request.method == 'POST':
        submitted = {t for t in request.form.getlist('equipment') if t in valid_names}
        notes = request.form.get('notes', '').strip()
        new_terrain_ids = _parse_locale_terrain(request.form)
        # #446 — explicit privacy override. The form posts `private=1` when the
        # athlete opts a shareable-category locale out of crowd-source sharing.
        # Residential categories are locked private regardless (the toggle is
        # hidden), so `_resolve_private` ORs the category default in. Only the
        # build/own modes carry the toggle; inherit mode leaves it untouched.
        opt_out = request.form.get('private') == '1'
        # Upsert the locale_profiles row — gym_profiles links + overrides FK
        # onto it. `edit_profile` already guaranteed the row exists, so this is
        # an UPDATE in practice; the ON CONFLICT stays defensive. `?::text[]`
        # cast: see the Bucket B #3 fix (psycopg2 list adapter landed empty
        # arrays in prod without it).
        db.execute(
            '''INSERT INTO locale_profiles (user_id, locale, notes, sharing_opt_out, locale_terrain_ids, updated_at)
               VALUES (?, ?, ?, ?, ?::text[], CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, locale) DO UPDATE SET
                 notes=excluded.notes,
                 sharing_opt_out=excluded.sharing_opt_out,
                 locale_terrain_ids=excluded.locale_terrain_ids,
                 updated_at=excluded.updated_at''',
            (uid, locale, notes, opt_out, new_terrain_ids)
        )
        # First-locale-auto-home (Track 1 §10) — the first locale saved
        # before any home exists becomes home.
        _ensure_home(db, uid, locale)
        if shared is None:
            # Build a new backing profile from this submission. Pass the
            # freshly submitted opt-out so the new profile's `private` reflects
            # this request (the `profile` row predates the upsert above).
            new_id = _create_gym_profile(db, uid, profile, submitted, valid_names,
                                         sharing_opt_out=opt_out)
            if new_id:
                _link_gym_profile(db, uid, locale, new_id)
        elif owns_shared:
            # The athlete's own profile — edit its equipment + privacy in place;
            # clear any stale overrides so the effective set is just the profile.
            if not gym_profile_id:
                _link_gym_profile(db, uid, locale, shared['id'])
            shared_category = shared['category'] if _row_has(shared, 'category') else None
            db.execute(
                'UPDATE gym_profiles SET equipment = ?, private = ? WHERE id = ?',
                (json.dumps(sorted(t for t in submitted if t in valid_names)),
                 _resolve_private(shared_category, opt_out),
                 shared['id']),
            )
            db.execute(
                'DELETE FROM locale_equipment_overrides WHERE user_id = ? AND locale = ?',
                (uid, locale),
            )
        else:
            # Inherit from a peer/shared base; persist per-athlete deltas.
            if not gym_profile_id:
                _link_gym_profile(db, uid, locale, shared['id'])
                _touch_gym_profile_confirmation(db, uid, shared['id'])
            _save_overrides(db, uid, locale, shared_tags, submitted, valid_names)
        db.commit()
        if sorted(new_terrain_ids) != sorted(prior_terrain_ids):
            _evict_layer2b_on_terrain_change(db, uid)
        if submitted != prior_effective:
            _evict_layer2c_on_equipment_change(db, uid)
        flash(f'Saved {profile["locale_name"] if profile and _row_has(profile, "locale_name") and profile["locale_name"] else locale} '
              f'({len(submitted)} items).', 'success')
        return redirect(url_for('locales.list_profiles'))

    # GET — effective set drives the checked state; inherit mode adds override
    # chips. `mode` keeps the template's existing branches working: 'legacy'
    # for own/build (plain save), 'shared_inherit' for peer inherit (override
    # chips).
    adds, removes = _load_overrides(db, uid, locale)
    mode = 'shared_inherit' if inherit else 'legacy'
    is_manual = bool(_row_has(profile, 'manual_entry') and profile['manual_entry'])
    is_mapbox_anchored = bool(_row_has(profile, 'mapbox_id') and profile['mapbox_id'])
    # #446 — privacy state for the form chip + opt-out toggle. The backing
    # category is the gym_profile's when the athlete owns one, else the
    # locale's. `privacy_locked` = residential (always private, no toggle);
    # otherwise the toggle reflects the stored sharing_opt_out.
    if owns_shared and _row_has(shared, 'category'):
        privacy_category = shared['category']
    elif _row_has(profile, 'category'):
        privacy_category = profile['category']
    else:
        privacy_category = None
    if owns_shared and _row_has(shared, 'private'):
        current_opt_out = bool(shared['private'])
    else:
        current_opt_out = bool(_row_has(profile, 'sharing_opt_out') and profile['sharing_opt_out'])
    privacy_locked = _category_default_private(privacy_category)
    return render_template('locales/form.html', mode=mode, locale=locale,
                           profile=profile,
                           equipment_categories=categories,
                           active=prior_effective,
                           shared_tags=shared_tags,
                           adds=adds, removes=removes,
                           shared=shared,
                           notes=(profile['notes'] if profile and profile['notes'] else ''),
                           is_manual=is_manual,
                           is_mapbox_anchored=is_mapbox_anchored,
                           is_deletable=True,
                           display_address=_display_address(profile),
                           privacy_locked=privacy_locked,
                           privacy_opt_out=current_opt_out,
                           privacy_effective=_resolve_private(privacy_category, current_opt_out),
                           terrain_choices=_terrain_choices(db),
                           active_terrain_ids=set(prior_terrain_ids),
                           # WS-H #581 Slice 5 — craft-kept-here capture (the (b)
                           # craft↔locale surface, relocated from event-windows).
                           craft_catalog=load_craft_catalog(),
                           crafts_here=load_craft_locales(db, uid).get(locale, []))


# ── D-59 — Mapbox-anchored locale creation ──────────────────────────────


@bp.route('/locales/new', methods=['GET', 'POST'])
def new_locale():
    """Athlete-typed Mapbox-anchored locale creation (D-59 §3 + §4).

    GET renders the search form (or the manual fallback when ?manual=1).
    Search results render in-template when ?q= is set and disclosure is
    acked. POST writes the selected Mapbox feature as a locale_profiles
    row, runs chain detection, and redirects to /locales/<slug>/nearby on
    a chain hit (D-59 §5) or back to /locales otherwise.
    """
    db = get_db()
    uid = current_user_id()
    if request.method == 'POST':
        return _save_mapbox_anchored(db, uid)
    _stash_return_to()
    manual = request.args.get('manual') == '1'
    query = (request.args.get('q') or '').strip()
    # D-59 §6 step 3 — `?upgrade=<slug>` lets athletes flip an existing
    # manual_entry=TRUE row to Mapbox-anchored. The upgrade row is shown
    # to the template + carried through the disclosure ack roundtrip + the
    # save POST as a hidden form field.
    upgrade_slug = (request.args.get('upgrade') or '').strip()
    upgrade_locale = None
    if upgrade_slug:
        upgrade_locale = db.execute(
            'SELECT * FROM locale_profiles WHERE user_id = ? AND locale = ?',
            (uid, upgrade_slug),
        ).fetchone()
        if not upgrade_locale:
            flash('Unknown location to upgrade.', 'danger')
            return redirect(url_for('locales.list_profiles'))
    acked = _disclosure_acked(db, uid)
    results: list[dict] = []
    error: str | None = None
    if query and acked and not manual:
        try:
            results = mapbox_client.search_places(query, limit=5)
        except mapbox_client.MapboxTokenMissing:
            error = 'Place lookup is not configured on the server. Use the manual entry option below.'
        except mapbox_client.MapboxNoResults:
            error = f'No matches for {query!r}. Try a broader search or use manual entry.'
        except mapbox_client.MapboxError as e:
            error = f'Place lookup unavailable ({e}). Try again or use manual entry.'
    return render_template('locales/new.html',
                           manual=manual, query=query,
                           acked=acked, results=results, error=error,
                           manual_categories=MANUAL_CATEGORIES,
                           residential_categories=sorted(RESIDENTIAL_CATEGORIES),
                           disclosure_version=MAPBOX_DISCLOSURE_VERSION,
                           upgrade_slug=upgrade_slug,
                           upgrade_locale=upgrade_locale)


@bp.route('/locales/new/acknowledge', methods=['POST'])
def acknowledge_mapbox_disclosure():
    """Records the Mapbox geocoding consent (D-59 §8) and redirects back
    to the search form. Re-acks (e.g. after a version bump) write a fresh
    row — the table allows duplicates and the `acked?` query takes the
    most recent."""
    db = get_db()
    uid = current_user_id()
    _record_disclosure_ack(db, uid)
    upgrade_slug = (request.form.get('upgrade_slug') or '').strip()
    if upgrade_slug:
        return redirect(url_for('locales.new_locale',
                                q=request.form.get('q', ''),
                                upgrade=upgrade_slug))
    return redirect(url_for('locales.new_locale', q=request.form.get('q', '')))


def _save_mapbox_anchored(db, uid: int):
    """POST /locales/new handler — INSERTs a Mapbox-anchored locale row
    (or UPDATEs in place when `upgrade_slug` is set per D-59 §6 step 3),
    runs chain detection, and decides where to redirect next."""
    upgrade_slug = (request.form.get('upgrade_slug') or '').strip()
    locale_name = (request.form.get('locale_name') or '').strip()
    mapbox_id = (request.form.get('mapbox_id') or '').strip()
    text = (request.form.get('text') or '').strip()
    place_name = (request.form.get('place_name') or '').strip()
    raw_payload = request.form.get('raw_payload') or ''
    # #446 — per-result opt-out: force this locale private even when Mapbox
    # returned a shareable category (e.g. a residence geocoded as a gym).
    opt_out = request.form.get('private') == '1'
    try:
        lng = float(request.form.get('lng') or '')
        lat = float(request.form.get('lat') or '')
    except ValueError:
        flash('Place lookup result was malformed; try again.', 'danger')
        return redirect(url_for('locales.new_locale', upgrade=upgrade_slug or None))
    if not locale_name or not mapbox_id:
        flash('Locale name and a place selection are required.', 'danger')
        return redirect(url_for('locales.new_locale', upgrade=upgrade_slug or None))
    chain = detect_chain(text)
    chain_id = chain['chain_id'] if chain else None
    chain_name = chain['canonical_name'] if chain else None
    # D-59 §4.2 step 3 — no chain match: derive category from Mapbox's
    # `properties.category` hint (gym/fitness/climbing → 'independent_gym'),
    # else NULL.
    if chain:
        category = chain['category']
    else:
        mb_category = (request.form.get('mapbox_category') or '').lower()
        if any(tok in mb_category for tok in ('gym', 'fitness', 'climbing')):
            category = 'independent_gym'
        else:
            category = None
    if upgrade_slug:
        # D-59 §6 step 3 — flip a manual_entry=TRUE row to Mapbox-anchored.
        # Slug stays the same so all FKs (locale_equipment, override rows)
        # remain valid; locale_name updates to the Mapbox feature's name
        # so the list view reflects what was looked up.
        existing = db.execute(
            'SELECT manual_entry FROM locale_profiles WHERE user_id = ? AND locale = ?',
            (uid, upgrade_slug),
        ).fetchone()
        if not existing:
            flash('Unknown location to upgrade.', 'danger')
            return redirect(url_for('locales.list_profiles'))
        # PR18 item C — block when this athlete already has a *different*
        # locale pointing at the same Mapbox feature.
        dup = _existing_locale_by_mapbox_id(db, uid, mapbox_id, exclude_slug=upgrade_slug)
        if dup:
            dup_label = dup['locale_name'] or dup['locale']
            flash(f'You already have a locale at this address ({dup_label}). Edit it instead.', 'warning')
            return redirect(url_for('locales.edit_profile', locale=dup['locale']))
        db.execute(
            '''UPDATE locale_profiles
               SET locale_name = ?, mapbox_id = ?, lat = ?, lng = ?,
                   chain_id = ?, chain_name = ?, category = ?,
                   manual_entry = FALSE, sharing_opt_out = ?,
                   place_payload = ?, place_fetched_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND locale = ?''',
            (locale_name, mapbox_id, lat, lng,
             chain_id, chain_name, category, opt_out,
             raw_payload or place_name,
             uid, upgrade_slug),
        )
        db.commit()
        flash(f'Upgraded {locale_name} with place data.', 'success')
        if chain_id:
            return redirect(url_for('locales.nearby_instances', locale=upgrade_slug))
        return _locale_flow_redirect()
    # PR18 item C — duplicate detection at create-time. If the athlete
    # already has a row pointing at the same Mapbox feature, redirect
    # them to edit the existing one instead of inserting a duplicate.
    dup = _existing_locale_by_mapbox_id(db, uid, mapbox_id)
    if dup:
        dup_label = dup['locale_name'] or dup['locale']
        flash(f'You already have a locale at this address ({dup_label}). Edit it instead.', 'warning')
        return redirect(url_for('locales.edit_profile', locale=dup['locale']))
    base_slug = _slugify(locale_name)
    if not base_slug:
        flash('Locale name needs at least one letter or number.', 'danger')
        return redirect(url_for('locales.new_locale'))
    slug = _unique_slug(db, uid, base_slug)
    db.execute(
        '''INSERT INTO locale_profiles
           (user_id, locale, locale_name, mapbox_id, lat, lng,
            chain_id, chain_name, category, manual_entry, sharing_opt_out,
            place_payload, place_fetched_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
        (uid, slug, locale_name, mapbox_id, lat, lng,
         chain_id, chain_name, category, opt_out, raw_payload or place_name),
    )
    _ensure_home(db, uid, slug)  # first-locale-auto-home (Track 1 §10)
    db.commit()
    flash(f'Saved {locale_name}.', 'success')
    if chain_id:
        return redirect(url_for('locales.nearby_instances', locale=slug))
    return _locale_flow_redirect()


@bp.route('/locales/new/manual', methods=['POST'])
def save_manual_locale():
    """Manual-entry path (D-59 §6). No Mapbox round-trip; coords +
    chain stay NULL; manual_entry=TRUE so plan-gen knows the row lacks
    proximity-cluster membership."""
    db = get_db()
    uid = current_user_id()
    locale_name = (request.form.get('locale_name') or '').strip()
    address = (request.form.get('address') or '').strip()
    category = (request.form.get('category') or '').strip()
    valid_categories = {c[0] for c in MANUAL_CATEGORIES}
    if category and category not in valid_categories:
        category = None
    # #446 — explicit opt-out for shareable categories. Residential categories
    # are private regardless; `_resolve_private` ORs the category default in
    # when the gym_profile is later built.
    opt_out = request.form.get('private') == '1'
    if not locale_name:
        flash('Locale name is required.', 'danger')
        return redirect(url_for('locales.new_locale', manual=1))
    # A manual locale must record *where* it is — an address-less row has no
    # coordinates and no place, so it can never resolve weather/clothing and
    # shows up as an empty location. Require the address (the Mapbox path
    # already guarantees a place via lat/lng).
    if not address:
        flash('An address is required so we know where this location is.', 'danger')
        return redirect(url_for('locales.new_locale', manual=1))
    base_slug = _slugify(locale_name)
    if not base_slug:
        flash('Locale name needs at least one letter or number.', 'danger')
        return redirect(url_for('locales.new_locale', manual=1))
    slug = _unique_slug(db, uid, base_slug)
    # #941 — the typed address has no Mapbox geocode (manual entry carries no
    # coords), so it can't drive weather; stash it in `place_payload` shaped
    # like a Mapbox feature so `_display_address` still renders it on the list /
    # form. Replaces the retired free-text `city` column.
    place_payload = (
        json.dumps({'properties': {'full_address': address}}) if address else None
    )
    db.execute(
        '''INSERT INTO locale_profiles
           (user_id, locale, locale_name, place_payload, notes,
            category, manual_entry, sharing_opt_out, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, TRUE, ?, CURRENT_TIMESTAMP)''',
        (uid, slug, locale_name, place_payload, '', category or None, opt_out),
    )
    _ensure_home(db, uid, slug)  # first-locale-auto-home (Track 1 §10)
    db.commit()
    flash(f'Saved {locale_name} (manual entry).', 'success')
    return _locale_flow_redirect()


@bp.route('/locales/<locale>/nearby', methods=['GET', 'POST'])
def nearby_instances(locale):
    """Post-anchor nearby chain-instance picker (D-59 §5). GET runs a
    proximity Mapbox query; POST INSERTs the opted-in instances by
    re-fetching and matching by mapbox_id."""
    db = get_db()
    uid = current_user_id()
    anchor = db.execute(
        'SELECT * FROM locale_profiles WHERE user_id = ? AND locale = ?',
        (uid, locale),
    ).fetchone()
    if not anchor:
        flash('Unknown location.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    chain_id = anchor['chain_id'] if 'chain_id' in anchor.keys() else None
    if not chain_id or anchor['lat'] is None or anchor['lng'] is None:
        # D-59 §4.2 — non-chain or manual-entry rows have no nearby surface.
        return _locale_flow_redirect()
    canonical = _canonical_name(chain_id) or anchor['chain_name'] or ''
    try:
        candidates = mapbox_client.search_nearby(
            canonical, float(anchor['lng']), float(anchor['lat']),
            limit=10,
        )
    except mapbox_client.MapboxError:
        # D-59 §3.4 — fail-open: no nearby surface, but the anchor row
        # itself is already saved.
        flash(f'Saved {anchor["locale_name"] or locale}; nearby search unavailable.', 'info')
        return _locale_flow_redirect()
    # D-59 §5 step 3 + 4 — keep only same-chain matches and exclude the
    # anchor itself by mapbox_id.
    same_chain: list[dict] = []
    for f in candidates:
        if f['mapbox_id'] == anchor['mapbox_id']:
            continue
        match = detect_chain(f['text'])
        if match and match['chain_id'] == chain_id:
            same_chain.append(f)
    if request.method == 'POST':
        selected_ids = set(request.form.getlist('mapbox_id'))
        selected = [f for f in same_chain if f['mapbox_id'] in selected_ids]
        # PR18 item C — skip selections this athlete already has saved at
        # the same mapbox_id. The D-60 inherit machinery handles the
        # duplicate gracefully (both link to the same gym_profile), but
        # the UX is confusing — better to surface "already saved" once
        # than to render two identical-looking rows on /locales.
        existing_ids = {r['mapbox_id'] for r in db.execute(
            'SELECT mapbox_id FROM locale_profiles WHERE user_id = ? AND mapbox_id IS NOT NULL',
            (uid,),
        ).fetchall() if r['mapbox_id']}
        skipped = len([f for f in selected if f['mapbox_id'] in existing_ids])
        selected = [f for f in selected if f['mapbox_id'] not in existing_ids]
        added = 0
        for f in selected:
            base_slug = _slugify(f['text'] or canonical)
            if not base_slug:
                continue
            slug = _unique_slug(db, uid, base_slug)
            db.execute(
                '''INSERT INTO locale_profiles
                   (user_id, locale, locale_name, mapbox_id, lat, lng,
                    chain_id, chain_name, category, manual_entry,
                    place_payload, place_fetched_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
                (uid, slug, f['text'] or canonical, f['mapbox_id'],
                 f['lat'], f['lng'], chain_id, canonical,
                 anchor['category'], f['raw_payload']),
            )
            added += 1
        db.commit()
        if added:
            flash(f'Added {added} nearby {canonical} location{"s" if added != 1 else ""}.', 'success')
        if skipped:
            flash(f'Skipped {skipped} already-saved location{"s" if skipped != 1 else ""}.', 'info')
        return _locale_flow_redirect()
    return render_template('locales/nearby.html',
                           anchor=anchor, canonical=canonical,
                           candidates=same_chain)


# ── D-59 §7 — on-demand Mapbox refresh ──────────────────────────────────


@bp.route('/locales/<locale>/refresh', methods=['POST'])
def refresh_from_mapbox(locale):
    """D-59 §7 on-demand refresh. POSTed from the edit screen / list view.
    PR18 item B: Phase 1 calls `/retrieve/{stored_mapbox_id}` directly
    instead of name-searching, so locales the athlete has renamed
    ("Horn's House" instead of "123 Main St") still refresh. If name +
    chain are unchanged, apply the fresh place_payload silently. If
    anything material changed, render a confirmation prompt so the
    athlete can opt in or out."""
    db = get_db()
    uid = current_user_id()
    profile = db.execute(
        'SELECT * FROM locale_profiles WHERE user_id = ? AND locale = ?',
        (uid, locale),
    ).fetchone()
    if not profile:
        flash('Unknown location.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    stored_mapbox_id = profile['mapbox_id'] if _row_has(profile, 'mapbox_id') else None
    if not stored_mapbox_id:
        flash('Only Mapbox-anchored locales can be refreshed.', 'warning')
        return redirect(url_for('locales.edit_profile', locale=locale))
    confirm = request.form.get('confirm') == '1'
    if confirm:
        # Apply phase — the refreshed data was embedded as hidden fields in
        # the confirm form. Trust those values (re-fetching here would
        # double the Mapbox call cost and might return different results
        # if Mapbox's index shifts mid-flow).
        new_text = (request.form.get('refresh_text') or '').strip()
        new_chain_id = (request.form.get('refresh_chain_id') or '').strip() or None
        new_chain_name = (request.form.get('refresh_chain_name') or '').strip() or None
        new_category = (request.form.get('refresh_category') or '').strip() or None
        new_payload = request.form.get('refresh_payload') or ''
        if not new_text:
            flash('Refresh confirmation was malformed; try again.', 'danger')
            return redirect(url_for('locales.list_profiles'))
        db.execute(
            '''UPDATE locale_profiles
               SET locale_name = ?, chain_id = ?, chain_name = ?, category = ?,
                   place_payload = ?, place_fetched_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND locale = ?''',
            (new_text, new_chain_id, new_chain_name, new_category,
             new_payload, uid, locale),
        )
        db.commit()
        flash(f'Refreshed {new_text}.', 'success')
        return redirect(url_for('locales.list_profiles'))
    # Fetch phase — PR18 item B. Old path used `search_nearby(locale_name,
    # lng, lat)` + match-by-id, which broke for athletes who renamed
    # locales ("Horn's House" returned zero matches). New path uses
    # `/retrieve/{mapbox_id}` directly, which is name-agnostic and queries
    # Mapbox's live state for the exact feature we stored.
    try:
        refreshed = mapbox_client.retrieve(
            stored_mapbox_id, session_token=uuid.uuid4().hex,
        )
    except mapbox_client.MapboxTokenMissing:
        flash('Place lookup is not configured on the server.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    except mapbox_client.MapboxNoResults:
        flash('Mapbox no longer returns this exact place. Edit the locale to relink.', 'warning')
        return redirect(url_for('locales.edit_profile', locale=locale))
    except mapbox_client.MapboxError as e:
        flash(f'Refresh failed: {e}.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    # Recompute chain + category from the refreshed feature.
    chain = detect_chain(refreshed['text'])
    new_chain_id = chain['chain_id'] if chain else None
    new_chain_name = chain['canonical_name'] if chain else None
    if chain:
        new_category = chain['category']
    else:
        mb_category = (refreshed['category'] or '').lower()
        if any(tok in mb_category for tok in ('gym', 'fitness', 'climbing')):
            new_category = 'independent_gym'
        else:
            new_category = profile['category'] if _row_has(profile, 'category') else None
    old_text = profile['locale_name'] if _row_has(profile, 'locale_name') else ''
    old_chain_id = profile['chain_id'] if _row_has(profile, 'chain_id') else None
    old_chain_name = profile['chain_name'] if _row_has(profile, 'chain_name') else None
    name_changed = refreshed['text'] and refreshed['text'] != old_text
    chain_changed = new_chain_id != old_chain_id
    if not (name_changed or chain_changed):
        # Silent path — refresh place_payload + bump place_fetched_at,
        # leave name/chain/category as-is.
        db.execute(
            '''UPDATE locale_profiles
               SET place_payload = ?, place_fetched_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND locale = ?''',
            (refreshed['raw_payload'], uid, locale),
        )
        db.commit()
        flash(f'Refreshed {old_text or locale} — no changes detected.', 'info')
        return redirect(url_for('locales.list_profiles'))
    return render_template('locales/refresh_confirm.html',
                           locale=locale, profile=profile,
                           refreshed=refreshed,
                           old_text=old_text,
                           old_chain_name=old_chain_name,
                           new_chain_id=new_chain_id,
                           new_chain_name=new_chain_name,
                           new_category=new_category,
                           name_changed=name_changed,
                           chain_changed=chain_changed)


# ── Track 1 — home (preferred) selection ───────────────────────────────


@bp.route('/locales/<locale>/home', methods=['POST'])
def make_home(locale):
    """Mark a locale as the athlete's home (`locale_profiles.preferred`).
    Atomically clears the previous home (Track 1 §10 — exactly one home). The
    plan-gen cone resolves the home + cluster from this flag."""
    db = get_db()
    uid = current_user_id()
    profile = db.execute(
        'SELECT 1 FROM locale_profiles WHERE user_id = ? AND locale = ?',
        (uid, locale),
    ).fetchone()
    if not profile:
        flash('Unknown location.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    _set_home(db, uid, locale)
    # Cluster/home inputs to Layer 2C changed — evict so the next plan-gen
    # re-derives the equipment pool from the new home.
    _evict_layer2c_on_equipment_change(db, uid)
    db.commit()
    flash('Home location updated.', 'success')
    return redirect(url_for('locales.list_profiles'))


# ── PR18 item D — delete with privacy-aware split rule ─────────────────


@bp.route('/locales/<locale>/delete', methods=['POST'])
def delete_locale(locale):
    """Delete an athlete-created locale. FK CASCADE on locale_profiles
    drops the dependent rows (locale_equipment, locale_equipment_overrides,
    locale_toggle_overrides) automatically.

    Residential split rule: home_gym + other_residence are private and
    never enterprise-shareable, so if one happens to have a linked
    gym_profiles row (defensive — under the current taxonomy residential
    locales don't enter the shared-profile flow at all), drop that
    gym_profiles row too. Chain + shared categories leave the shared
    gym_profiles row intact so enterprise data is preserved for other
    athletes.

    All locales are athlete-created and deletable (the legacy enum slots
    that used to be undeletable are retired, WS-B).
    """
    db = get_db()
    uid = current_user_id()
    profile = db.execute(
        '''SELECT category, gym_profile_id, locale_name
           FROM locale_profiles WHERE user_id = ? AND locale = ?''',
        (uid, locale),
    ).fetchone()
    if not profile:
        flash('Unknown location.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    gym_profile_id = (
        profile['gym_profile_id'] if _row_has(profile, 'gym_profile_id') else None
    )
    display = (
        profile['locale_name']
        if _row_has(profile, 'locale_name') and profile['locale_name']
        else locale
    )
    # Track 1 — the legacy `locale_equipment` table is gone; the only
    # locale-scoped dependents now are locale_equipment_overrides +
    # locale_toggle_overrides, both ON DELETE CASCADE, so the parent DELETE
    # cleans them up implicitly.
    db.execute(
        'DELETE FROM locale_profiles WHERE user_id = ? AND locale = ?',
        (uid, locale),
    )
    # Privacy split rule keyed on the explicit `private` flag (#446), not the
    # locale category: a private, athlete-owned gym_profile is personal data
    # (a residence, or a shareable-category place the athlete opted out of
    # sharing) and goes away with the locale. A shared (non-private) profile is
    # preserved so peer/enterprise data survives for other athletes.
    if gym_profile_id:
        db.execute(
            '''DELETE FROM gym_profiles
               WHERE id = ? AND created_by_user_id = ?
                 AND COALESCE(private, FALSE) = TRUE''',
            (gym_profile_id, uid),
        )
    db.commit()
    flash(f'Deleted {display}.', 'success')
    return redirect(url_for('locales.list_profiles'))
