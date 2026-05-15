import re

from flask import Blueprint, render_template, request, redirect, url_for, flash

import database
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

# D-59 §6 — manual-entry category dropdown values. Subset of the D-60 §3
# taxonomy that's meaningful when chain detection is bypassed.
MANUAL_CATEGORIES = (
    ('commercial_chain_gym', 'Commercial chain gym'),
    ('independent_gym', 'Independent gym'),
    ('home_gym', 'Home gym'),
    ('hotel_gym', 'Hotel gym'),
    ('climbing_gym', 'Climbing gym'),
    ('outdoor', 'Outdoor (trail/park)'),
    ('other', 'Other'),
)


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
    if not database._is_postgres():
        return True
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
    if not database._is_postgres():
        return
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
    return render_template('locales/list.html', locales=displayed_locales,
                           legacy_locales=LOCALES, profiles=profiles,
                           equipment_categories=EQUIPMENT_CATEGORIES,
                           tags_by_locale=tags_by_locale, counts=counts)


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
        # CURRENT_TIMESTAMP is portable; datetime('now') is SQLite-only and
        # blew up the UPSERT on Postgres. ON CONFLICT works on both backends.
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
    profile = db.execute(
        'SELECT * FROM locale_profiles WHERE locale=? AND user_id=?',
        (locale, uid)
    ).fetchone()
    active_rows = db.execute(
        '''SELECT ei.tag FROM locale_equipment le
           JOIN equipment_items ei ON ei.id = le.equipment_id
           WHERE le.user_id = ? AND le.locale = ?''',
        (uid, locale)
    ).fetchall()
    active = {row['tag'] for row in active_rows}
    return render_template('locales/form.html', locale=locale,
                           equipment_categories=EQUIPMENT_CATEGORIES,
                           active=active,
                           notes=profile['notes'] if profile else '',
                           city=profile['city'] if profile and profile['city'] else '')


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
                           disclosure_version=MAPBOX_DISCLOSURE_VERSION)


@bp.route('/locales/new/acknowledge', methods=['POST'])
def acknowledge_mapbox_disclosure():
    """Records the Mapbox geocoding consent (D-59 §8) and redirects back
    to the search form. Re-acks (e.g. after a version bump) write a fresh
    row — the table allows duplicates and the `acked?` query takes the
    most recent."""
    db = get_db()
    uid = current_user_id()
    _record_disclosure_ack(db, uid)
    return redirect(url_for('locales.new_locale', q=request.form.get('q', '')))


def _save_mapbox_anchored(db, uid: int):
    """POST /locales/new handler — INSERTs a Mapbox-anchored locale row,
    runs chain detection, and decides where to redirect next."""
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
        return redirect(url_for('locales.new_locale'))
    if not locale_name or not mapbox_id:
        flash('Locale name and a place selection are required.', 'danger')
        return redirect(url_for('locales.new_locale'))
    base_slug = _slugify(locale_name)
    if not base_slug:
        flash('Locale name needs at least one letter or number.', 'danger')
        return redirect(url_for('locales.new_locale'))
    slug = _unique_slug(db, uid, base_slug)
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
        return redirect(url_for('locales.list_profiles'))
    return render_template('locales/nearby.html',
                           anchor=anchor, canonical=canonical,
                           candidates=same_chain)
