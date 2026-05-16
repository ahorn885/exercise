import json
import re
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash

import mapbox_client
from chain_registry import GYM_CHAINS, detect_chain
from database import get_db
from init_db import EQUIPMENT_CATEGORIES
from routes.auth import current_user_id

bp = Blueprint('locales', __name__)

LOCALES = ['home', 'hotel', 'partner', 'airport']

# Flat set of all valid tag keys for input validation
ALL_TAGS = {tag for _, items in EQUIPMENT_CATEGORIES for tag, _ in items}

# D-59 §8 — disclosure_id stored in disclosure_acknowledgments. Bumped only
# when the disclosure copy materially changes; athletes re-acknowledge on
# bump.
MAPBOX_DISCLOSURE_ID = 'mapbox_geocoding_consent'
MAPBOX_DISCLOSURE_VERSION = 'v1'

# D-60 §3 — locale category taxonomy. Manual-entry dropdown surfaces the
# whole taxonomy so athletes can pick the right value when bypassing chain
# detection. The eight shared-profile categories (SHARED_PROFILE_CATEGORIES
# below) gate the inherit/override UI on the edit screen. PR18 reclassified
# outdoor_park into shared-profile: the privacy boundary is residence-vs-
# public, not gym-vs-non-gym — parks with verifiable Mapbox addresses are
# publicly shareable.
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

# D-60 §3 — categories that expect a shared gym_profiles row. The
# remaining two (home_gym, other_residence) stay per-athlete + private;
# their equipment lives in legacy `locale_equipment` and they're never
# enterprise-shareable.
SHARED_PROFILE_CATEGORIES = frozenset({
    'commercial_chain_gym', 'independent_gym', 'hotel_gym',
    'climbing_gym_chain', 'climbing_gym_indie',
    'pool_indoor', 'pool_outdoor', 'outdoor_park',
})

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
    locale the athlete can pick — legacy enum slots (home/hotel/partner/
    airport) always present + athlete-created rows. `bucket` is the
    where_available analog used by /references filter logic; for legacy slugs
    bucket == slug, for custom slugs bucket comes from
    CATEGORY_TO_WHERE_AVAILABLE_BUCKET (may be '' when no Layer 0 analog).
    """
    rows = db.execute(
        'SELECT locale, locale_name, category FROM locale_profiles '
        'WHERE user_id = ?',
        (uid,),
    ).fetchall()
    by_slug = {r['locale']: r for r in rows}

    choices = []
    for slug in LOCALES:
        row = by_slug.get(slug)
        label = (row['locale_name'] if row and row['locale_name'] else slug.capitalize())
        choices.append({'slug': slug, 'label': label, 'bucket': slug})
    for slug in sorted(s for s in by_slug if s not in LOCALES):
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


def _is_shared_profile_locale(profile_row) -> bool:
    """True when this locale should use the D-60 gym_profiles inherit/
    override model. False for legacy enums, manual-entry rows, private
    residential categories (home_gym/other_residence), and any row
    missing a mapbox_id (no stable join key for the shared profile)."""
    if not profile_row:
        return False
    if not _row_has(profile_row, 'category') or not _row_has(profile_row, 'mapbox_id'):
        return False
    category = profile_row['category']
    if category not in SHARED_PROFILE_CATEGORIES:
        return False
    if not profile_row['mapbox_id']:
        return False
    if _row_has(profile_row, 'manual_entry') and profile_row['manual_entry']:
        return False
    return True


def _find_gym_profile(db, mapbox_id):
    """Look up the shared gym profile keyed by mapbox_id (D-60 §4.1). Returns
    the row or None. mapbox_id is UNIQUE on gym_profiles."""
    if not mapbox_id:
        return None
    return db.execute(
        'SELECT * FROM gym_profiles WHERE mapbox_id = ?',
        (mapbox_id,),
    ).fetchone()


def _shared_equipment_set(profile_row) -> set:
    """Parse gym_profiles.equipment (JSON array) into a tag set."""
    if not profile_row or not _row_has(profile_row, 'equipment'):
        return set()
    payload = profile_row['equipment']
    if not payload:
        return set()
    try:
        tags = json.loads(payload)
    except (ValueError, TypeError):
        return set()
    return {t for t in tags if isinstance(t, str) and t in ALL_TAGS}


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


def _effective_equipment(shared_tags: set, adds: set, removes: set) -> set:
    """Per D-60 §4.4: (shared ∪ adds) ∖ removes."""
    return (set(shared_tags) | set(adds)) - set(removes)


def _save_overrides(db, uid: int, locale: str, shared_tags: set, athlete_tags: set) -> None:
    """Replace this athlete's overrides on this locale with the diff of
    athlete_tags vs. shared_tags. Atomic-per-locale: DELETE-then-INSERT."""
    db.execute(
        'DELETE FROM locale_equipment_overrides WHERE user_id = ? AND locale = ?',
        (uid, locale),
    )
    adds = athlete_tags - shared_tags
    removes = shared_tags - athlete_tags
    for tag in adds:
        if tag in ALL_TAGS:
            db.execute(
                '''INSERT INTO locale_equipment_overrides
                   (user_id, locale, equipment_tag, action)
                   VALUES (?, ?, ?, ?)''',
                (uid, locale, tag, 'add'),
            )
    for tag in removes:
        if tag in ALL_TAGS:
            db.execute(
                '''INSERT INTO locale_equipment_overrides
                   (user_id, locale, equipment_tag, action)
                   VALUES (?, ?, ?, ?)''',
                (uid, locale, tag, 'remove'),
            )


def _create_gym_profile(db, uid: int, profile_row, equipment_tags: set):
    """First-athlete-at-this-mapbox flow (D-60 §4.2). Creates a new
    gym_profiles row with `equipment` as JSON and returns the new id.
    Caller links via locale_profiles.gym_profile_id."""
    equipment_json = json.dumps(sorted(t for t in equipment_tags if t in ALL_TAGS))
    display = profile_row['locale_name'] if _row_has(profile_row, 'locale_name') else None
    category = profile_row['category'] if _row_has(profile_row, 'category') else None
    mapbox_id = profile_row['mapbox_id'] if _row_has(profile_row, 'mapbox_id') else None
    row = db.execute(
        '''INSERT INTO gym_profiles
           (mapbox_id, display_name, category, equipment,
            created_by_user_id, last_confirmed_by, last_confirmed_at,
            contribution_count, private)
           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1, FALSE)
           RETURNING id''',
        (mapbox_id, display, category, equipment_json, uid, uid),
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


@bp.route('/locales')
def list_profiles():
    db = get_db()
    uid = current_user_id()
    # locale_profiles is parent-scoped; locale_equipment is parent-JOIN scoped
    # via locale_profiles. Session 3 makes the locale PK composite (user_id, locale)
    # so users can have independent locales — until then, the global PK means a
    # user 2 can't claim a locale name user 1 already owns.
    profiles = {
        r['locale']: r for r in db.execute(
            'SELECT * FROM locale_profiles WHERE user_id = ?', (uid,)
        ).fetchall()
    }
    # Display: legacy enums first, then athlete-created (D-59) rows in
    # creation order. Mixed list keeps the existing 4-card v1 UX while
    # surfacing rows from /locales/new alongside.
    custom_locales = [k for k in profiles.keys() if k not in LOCALES]
    custom_locales.sort()
    displayed_locales = list(LOCALES) + custom_locales
    tags_by_locale = {}
    for row in db.execute(
        '''SELECT le.locale, ei.tag, ei.label
           FROM locale_equipment le
           JOIN equipment_items ei ON ei.id = le.equipment_id
           WHERE le.user_id = ?
           ORDER BY le.locale, ei.category, ei.label''',
        (uid,)
    ).fetchall():
        tags_by_locale.setdefault(row['locale'], []).append(
            {'tag': row['tag'], 'label': row['label']}
        )
    counts = {loc: len(items) for loc, items in tags_by_locale.items()}
    display_addresses = {loc: _display_address(p) for loc, p in profiles.items()}
    return render_template('locales/list.html', locales=displayed_locales,
                           legacy_locales=LOCALES, profiles=profiles,
                           equipment_categories=EQUIPMENT_CATEGORIES,
                           tags_by_locale=tags_by_locale, counts=counts,
                           display_addresses=display_addresses)


@bp.route('/locales/<locale>/edit', methods=['GET', 'POST'])
def edit_profile(locale):
    db = get_db()
    uid = current_user_id()
    # Legacy enum locales auto-create on first save (existing v1 behaviour);
    # athlete-created (D-59) locales must already exist for this user.
    if locale not in LOCALES:
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
    # D-60 §4 — branch into the shared-profile path when the locale's
    # category is one of the seven gym/pool flavors and we have a stable
    # mapbox_id to key on. Legacy enums (home/hotel/partner/airport),
    # manual-entry rows, and no-shared-profile categories fall through to
    # the legacy locale_equipment path.
    if _is_shared_profile_locale(profile):
        return _edit_shared_locale(db, uid, locale, profile)
    return _edit_legacy_locale(db, uid, locale, profile)


def _edit_legacy_locale(db, uid: int, locale: str, profile):
    """Legacy per-athlete `locale_equipment` flow (pre-D-60). Used for
    legacy enums, manual-entry rows, and no-shared-profile categories
    (home_gym, outdoor_park, other_residence)."""
    if request.method == 'POST':
        selected_tags = [t for t in request.form.getlist('equipment') if t in ALL_TAGS]
        notes = request.form.get('notes', '').strip()
        city = request.form.get('city', '').strip()
        # Resolve tags to equipment_ids (shared catalog)
        if selected_tags:
            placeholders = ','.join('?' * len(selected_tags))
            eq_rows = db.execute(
                f'SELECT id, tag FROM equipment_items WHERE tag IN ({placeholders})',
                selected_tags
            ).fetchall()
            tag_to_id = {r['tag']: r['id'] for r in eq_rows}
        else:
            tag_to_id = {}
        # Upsert locale_profiles first — locale_equipment has an FK on this
        # table. PK is composite (user_id, locale) since Session 3.
        db.execute(
            '''INSERT INTO locale_profiles (user_id, locale, notes, city, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, locale) DO UPDATE SET
                 notes=excluded.notes,
                 city=excluded.city,
                 updated_at=excluded.updated_at''',
            (uid, locale, notes, city)
        )
        # Replace locale_equipment rows atomically (scoped per-user)
        db.execute(
            'DELETE FROM locale_equipment WHERE user_id = ? AND locale = ?',
            (uid, locale)
        )
        for tag in selected_tags:
            eq_id = tag_to_id.get(tag)
            if eq_id:
                db.execute(
                    'INSERT INTO locale_equipment (user_id, locale, equipment_id) VALUES (?, ?, ?)',
                    (uid, locale, eq_id)
                )
        db.commit()
        flash(f'{locale.title()} profile saved ({len(selected_tags)} items).', 'success')
        return redirect(url_for('locales.list_profiles'))
    # GET — load active equipment from locale_equipment (parent-JOIN scoped)
    active_rows = db.execute(
        '''SELECT ei.tag FROM locale_equipment le
           JOIN equipment_items ei ON ei.id = le.equipment_id
           WHERE le.user_id = ? AND le.locale = ?''',
        (uid, locale)
    ).fetchall()
    active = {row['tag'] for row in active_rows}
    is_manual = bool(_row_has(profile, 'manual_entry') and profile['manual_entry'])
    is_mapbox_anchored = bool(_row_has(profile, 'mapbox_id') and profile['mapbox_id'])
    is_deletable = locale not in LOCALES
    return render_template('locales/form.html', mode='legacy', locale=locale,
                           profile=profile,
                           equipment_categories=EQUIPMENT_CATEGORIES,
                           active=active,
                           notes=profile['notes'] if profile else '',
                           city=profile['city'] if profile and profile['city'] else '',
                           is_manual=is_manual,
                           is_mapbox_anchored=is_mapbox_anchored,
                           is_deletable=is_deletable,
                           display_address=_display_address(profile))


def _edit_shared_locale(db, uid: int, locale: str, profile):
    """D-60 §4.2/§4.3/§4.4 — shared gym profile inherit/override flow.
    First athlete at this mapbox_id creates the gym_profiles row; subsequent
    athletes inherit and write deltas to locale_equipment_overrides."""
    mapbox_id = profile['mapbox_id']
    gym_profile_id = profile['gym_profile_id'] if _row_has(profile, 'gym_profile_id') else None
    shared = None
    if gym_profile_id:
        shared = db.execute(
            'SELECT * FROM gym_profiles WHERE id = ?',
            (gym_profile_id,),
        ).fetchone()
    if not shared:
        # No FK yet — look up a peer profile for this mapbox_id (another
        # athlete may have built one). If found, treat this as the inherit
        # case and link the FK on first save.
        shared = _find_gym_profile(db, mapbox_id)
    shared_tags = _shared_equipment_set(shared)
    if request.method == 'POST':
        submitted = {t for t in request.form.getlist('equipment') if t in ALL_TAGS}
        notes = request.form.get('notes', '').strip()
        if not shared:
            # First athlete here — build the shared profile from this
            # athlete's submission. Athlete's effective view becomes the
            # base; no overrides yet.
            new_id = _create_gym_profile(db, uid, profile, submitted)
            if new_id:
                _link_gym_profile(db, uid, locale, new_id)
            db.execute(
                '''UPDATE locale_profiles
                   SET notes = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND locale = ?''',
                (notes, uid, locale),
            )
            db.commit()
            flash(f'Built the equipment profile for {profile["locale_name"] or locale} ({len(submitted)} items).', 'success')
            return redirect(url_for('locales.list_profiles'))
        # Inherit case — link FK if not yet linked, then save deltas vs.
        # the shared base.
        if not gym_profile_id:
            _link_gym_profile(db, uid, locale, shared['id'])
            _touch_gym_profile_confirmation(db, uid, shared['id'])
        _save_overrides(db, uid, locale, shared_tags, submitted)
        db.execute(
            '''UPDATE locale_profiles
               SET notes = ?, updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND locale = ?''',
            (notes, uid, locale),
        )
        db.commit()
        flash(f'Saved your view of {profile["locale_name"] or locale} ({len(submitted)} items).', 'success')
        return redirect(url_for('locales.list_profiles'))
    # GET — render either the build-new form or the inherit-with-overrides
    # form. Effective view drives the pre-checked state.
    adds, removes = _load_overrides(db, uid, locale)
    effective = _effective_equipment(shared_tags, adds, removes) if shared else set()
    mode = 'shared_inherit' if shared else 'shared_build'
    return render_template('locales/form.html', mode=mode, locale=locale,
                           profile=profile,
                           equipment_categories=EQUIPMENT_CATEGORIES,
                           active=effective,
                           shared_tags=shared_tags,
                           adds=adds, removes=removes,
                           shared=shared,
                           notes=profile['notes'] if profile and profile['notes'] else '',
                           city=profile['city'] if profile and profile['city'] else '',
                           is_manual=False,
                           is_mapbox_anchored=True,
                           is_deletable=locale not in LOCALES,
                           display_address=_display_address(profile))


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
                   manual_entry = FALSE,
                   place_payload = ?, place_fetched_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND locale = ?''',
            (locale_name, mapbox_id, lat, lng,
             chain_id, chain_name, category,
             raw_payload or place_name,
             uid, upgrade_slug),
        )
        db.commit()
        flash(f'Upgraded {locale_name} with place data.', 'success')
        if chain_id:
            return redirect(url_for('locales.nearby_instances', locale=upgrade_slug))
        return redirect(url_for('locales.list_profiles'))
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
            chain_id, chain_name, category, manual_entry,
            place_payload, place_fetched_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
        (uid, slug, locale_name, mapbox_id, lat, lng,
         chain_id, chain_name, category, raw_payload or place_name),
    )
    db.commit()
    flash(f'Saved {locale_name}.', 'success')
    if chain_id:
        return redirect(url_for('locales.nearby_instances', locale=slug))
    return redirect(url_for('locales.list_profiles'))


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
    if not locale_name:
        flash('Locale name is required.', 'danger')
        return redirect(url_for('locales.new_locale', manual=1))
    base_slug = _slugify(locale_name)
    if not base_slug:
        flash('Locale name needs at least one letter or number.', 'danger')
        return redirect(url_for('locales.new_locale', manual=1))
    slug = _unique_slug(db, uid, base_slug)
    db.execute(
        '''INSERT INTO locale_profiles
           (user_id, locale, locale_name, city, notes,
            category, manual_entry, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, TRUE, CURRENT_TIMESTAMP)''',
        (uid, slug, locale_name, address, '', category or None),
    )
    db.commit()
    flash(f'Saved {locale_name} (manual entry).', 'success')
    return redirect(url_for('locales.list_profiles'))


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
        return redirect(url_for('locales.list_profiles'))
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
        return redirect(url_for('locales.list_profiles'))
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
        return redirect(url_for('locales.list_profiles'))
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

    Legacy enum slugs (home/hotel/partner/airport) are not deletable
    here — they auto-render on /locales independent of any row, and the
    delete UI is gated behind the athlete-created edit screen.
    """
    db = get_db()
    uid = current_user_id()
    if locale in LOCALES:
        flash('Legacy locale slots cannot be deleted.', 'warning')
        return redirect(url_for('locales.edit_profile', locale=locale))
    profile = db.execute(
        '''SELECT category, gym_profile_id, locale_name
           FROM locale_profiles WHERE user_id = ? AND locale = ?''',
        (uid, locale),
    ).fetchone()
    if not profile:
        flash('Unknown location.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    category = profile['category'] if _row_has(profile, 'category') else None
    gym_profile_id = (
        profile['gym_profile_id'] if _row_has(profile, 'gym_profile_id') else None
    )
    display = (
        profile['locale_name']
        if _row_has(profile, 'locale_name') and profile['locale_name']
        else locale
    )
    db.execute(
        'DELETE FROM locale_profiles WHERE user_id = ? AND locale = ?',
        (uid, locale),
    )
    if category in ('home_gym', 'other_residence') and gym_profile_id:
        db.execute(
            '''DELETE FROM gym_profiles
               WHERE id = ? AND created_by_user_id = ?''',
            (gym_profile_id, uid),
        )
    db.commit()
    flash(f'Deleted {display}.', 'success')
    return redirect(url_for('locales.list_profiles'))
