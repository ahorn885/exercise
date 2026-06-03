"""Render smoke tests for the redesign Locations forms (Phase 6 secondary
forms): the equipment editor (`locales/form.html`, all three modes) and the
add-location flow (`locales/new.html`, all three states).

The `edit_profile` / `new_locale` routes run intricate query paths (shared
profiles, overrides, terrain, Mapbox), so rather than mock all of that we
render the templates directly through the booted app's Jinja env inside a
request context — this still exercises the full new shell (base.html, sidebar,
topbar, context processors) and catches template/CSP regressions.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import flask  # noqa: E402
import app as _appmod  # noqa: E402


def _render(template, **ctx):
    with _appmod.app.test_request_context('/'):
        flask.g.current_user_row = {'id': 1, 'username': 'owner',
                                    'display_name': 'Owner'}
        return flask.render_template(template, **ctx)


# ─── locales/form.html ──────────────────────────────────────────────────

_EQUIP = [('Free weights', [('db', 'Dumbbells'), ('bb', 'Barbell')])]
_TERRAIN = [{'id': 'trail', 'label': 'Trail'}, {'id': 'road', 'label': 'Road'}]


def _form_ctx(**kw):
    base = dict(
        mode='legacy', locale='home',
        profile={'locale_name': None, 'chain_name': None, 'category': None,
                 'notes': '', 'city': ''},
        equipment_categories=_EQUIP, active={'db'},
        notes='', city='', is_manual=False, is_mapbox_anchored=False,
        is_deletable=False, display_address='',
        terrain_choices=_TERRAIN, active_terrain_ids={'trail'},
    )
    base.update(kw)
    return base


def test_form_legacy_renders():
    html = _render('locales/form.html', **_form_ctx())
    assert 'app-shell' in html
    assert 'Location equipment' in html
    # Field names preserved for the POST handler.
    assert 'name="equipment"' in html
    assert 'name="locale_terrain_ids"' in html
    assert 'name="city"' in html          # legacy-only field present
    assert 'name="notes"' in html
    assert 'Dumbbells' in html and 'Trail' in html
    # No shared-profile override chips in legacy mode.
    assert '+ override' not in html
    assert 'style="' not in html and 'onclick=' not in html


def test_form_shared_inherit_shows_override_chips():
    html = _render('locales/form.html', **_form_ctx(
        mode='shared_inherit',
        profile={'locale_name': 'Planet Fitness', 'chain_name': 'Planet Fitness',
                 'category': None, 'notes': '', 'city': ''},
        active={'db'}, shared_tags={'bb'}, adds={'db'}, removes=set(),
        shared={'last_confirmed_at': '2026-05-01', 'contribution_count': 3},
        is_mapbox_anchored=True,
    ))
    assert 'app-shell' in html
    assert '+ override' in html        # 'db' is an add on top of shared
    assert 'shared' in html            # 'bb' inherited
    assert 'Inherited from the shared profile' in html
    # shared modes are not legacy → no city field.
    assert 'name="city"' not in html
    assert 'style="' not in html


def test_form_deletable_shows_delete():
    html = _render('locales/form.html', **_form_ctx(is_deletable=True))
    assert '/locales/home/delete' in html
    assert 'data-confirm=' in html     # delete still confirms
    assert 'style="' not in html


# ─── locales/new.html ───────────────────────────────────────────────────

def _new_ctx(**kw):
    base = dict(manual=False, query='', acked=True, results=[], error=None,
                manual_categories=[('home', 'Home gym')],
                disclosure_version='v1', upgrade_slug='', upgrade_locale=None)
    base.update(kw)
    return base


def test_new_manual_renders():
    html = _render('locales/new.html', **_new_ctx(manual=True))
    assert 'app-shell' in html
    assert 'name="locale_name"' in html
    assert 'name="address"' in html
    assert 'name="category"' in html
    assert '/locales/new/manual' in html
    assert 'style="' not in html


def test_new_disclosure_gate_renders():
    html = _render('locales/new.html', **_new_ctx(acked=False, query='gym'))
    assert 'Place lookup uses Mapbox' in html
    assert '/locales/new/acknowledge' in html
    assert 'Acknowledge' in html
    assert 'style="' not in html


def test_new_search_results_render():
    results = [{'text': 'Planet Fitness', 'place_name': '123 Main St',
                'mapbox_id': 'poi.1'}]
    html = _render('locales/new.html', **_new_ctx(query='planet', results=results))
    assert 'name="q"' in html                 # search field
    assert 'Planet Fitness' in html
    assert 'name="mapbox_id"' in html          # per-result save form
    assert 'Save this' in html
    assert 'style="' not in html and 'onclick=' not in html


# ─── locales/nearby.html + refresh_confirm.html ─────────────────────────

def test_nearby_renders_candidates():
    candidates = [{'mapbox_id': 'poi.1', 'text': 'Planet Fitness Uptown',
                   'place_name': '99 Lake St'}]
    html = _render('locales/nearby.html', canonical='Planet Fitness',
                   anchor={'locale_name': 'PF Downtown', 'locale': 'pf-dt'},
                   candidates=candidates)
    assert 'app-shell' in html
    assert 'name="mapbox_id"' in html
    assert 'Planet Fitness Uptown' in html
    assert 'Add selected' in html
    assert 'style="' not in html and 'onclick=' not in html


def test_refresh_confirm_renders_diff():
    html = _render('locales/refresh_confirm.html', locale='pf-dt',
                   profile={'locale_name': 'PF Downtown'},
                   refreshed={'text': 'Planet Fitness — Downtown', 'raw_payload': '{}'},
                   old_text='Planet Fitness', old_chain_name='Planet Fitness',
                   new_chain_id='pf', new_chain_name='Planet Fitness',
                   new_category='gym', name_changed=True, chain_changed=False)
    assert 'app-shell' in html
    # All hidden POST fields preserved for the confirm roundtrip.
    for name in ('confirm', 'refresh_text', 'refresh_chain_id',
                 'refresh_chain_name', 'refresh_category', 'refresh_payload'):
        assert 'name="%s"' % name in html
    assert 'Yes, update' in html
    assert 'Planet Fitness — Downtown' in html
    assert 'style="' not in html
